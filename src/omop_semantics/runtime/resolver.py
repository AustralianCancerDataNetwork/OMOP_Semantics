from omop_semantics.schema.generated_models.omop_semantic_registry import (
    OmopConcept, 
    OmopGroup, 
    OmopEnum, 
    RegistryFragment, 
    OmopSemanticObject, 
    OmopTemplate,
    OmopCdmProfile
)
from pathlib import Path
from dataclasses import dataclass
from typing import Iterable, TypedDict, Optional, Set
from .renderers import render_semantic_object, render_profile_object, Html, tr, h, table, as_list, render_compiled_templates
from .instance_loader import load_registry_fragment, merge_registry_fragments, load_symbol_module


class CompiledTemplate(TypedDict):
    """
    A compiled, execution-ready representation of an OMOP semantic template.

    This structure is produced by the runtime compiler layer and contains
    only the information required for downstream execution in ETL pipelines,
    query builders, or data loaders. In particular, semantic objects
    (e.g. OmopGroup, OmopEnum) are resolved into concrete OMOP concept IDs.

    Fields
    ------
    name
        Human-readable name of the template.
    role
        Semantic role of the template (e.g. 'demographic', 'staging', 'outcome').
    cdm_profile
        The OMOP CDM profile describing which table and slots this template maps to.
    entity_concept_ids
        Set of OMOP concept_ids that are valid for the entity concept slot.
    value_concept_ids
        Optional set of OMOP concept_ids that are valid for the value slot.
    """
    name: str
    role: str
    cdm_profile: OmopCdmProfile
    entity_concept_ids: Set[int]
    value_concept_ids: Optional[Set[int]]


class OmopSemanticResolver:
    """
    Resolves OMOP semantic objects into concrete OMOP concept identifiers.

    This class provides the semantic grounding layer between declarative
    semantic objects (e.g. OmopConcept, OmopGroup, OmopEnum) and the
    executable representation required by OMOP-based ETL and query logic.

    The resolver is intentionally minimal and explainable:
    - OmopConcept resolves to its single concept_id
    - OmopEnum resolves to the set of concept_ids of its members
    - OmopGroup resolves to the anchor (parent) concept_ids of the group

    This library is not database-backed so the resolved group hierarchies
    need to be resolved in downstream logic.

    TODO: allow this class to extended with full resolution logic without
    introducing dependencies on database connections or external services. 
    """
    def resolve(self, obj: OmopSemanticObject) -> set[int]:
        """
        Resolve a semantic object into a set of OMOP concept identifiers.

        Parameters
        ----------
        obj
            A semantic object describing permissible OMOP concepts.

        Returns
        -------
        set[int]
            A set of OMOP concept_ids derived from the semantic object.

        Raises
        ------
        ValueError
            If a required concept_id is missing.
        TypeError
            If the semantic object type is unsupported.
        """
        if isinstance(obj, OmopConcept):
            if obj.concept_id is None:
                raise ValueError(f"OmopConcept has no concept_id: {obj}")
            return {obj.concept_id}

        if isinstance(obj, OmopEnum):
            return {
                c.concept_id
                for c in obj.enum_members
                if c.concept_id is not None
            }
        
        if isinstance(obj, OmopGroup):
            # Return only the anchor concepts for the group
            return {
                parent.concept_id
                for parent in (obj.parent_concepts or [])
                if parent.concept_id is not None
            }

        raise TypeError(f"Unsupported semantic object: {type(obj)}")

class OmopTemplateRuntime:
    """
    Runtime compiler for OMOP semantic templates.

    This class transforms declarative OmopTemplate instances into
    compiled, execution-ready representations by resolving semantic
    objects into concrete OMOP concept identifiers using an
    OmopSemanticResolver.

    The output of this layer is intended to be consumed directly by
    ETL pipelines, query builders, or analytics workflows.
    """
    def __init__(self, resolver: OmopSemanticResolver):
        """
        Create a runtime compiler bound to a semantic resolver.

        Parameters
        ----------
        resolver
            Resolver used to ground semantic objects into OMOP concept IDs.
        """
        self.resolver = resolver

    def compile(self, tpl: OmopTemplate) -> CompiledTemplate:
        """
        Compile a declarative OMOP template into a runtime representation.

        Parameters
        ----------
        tpl
            Declarative semantic template describing how concepts map to OMOP CDM slots.

        Returns
        -------
        CompiledTemplate
            Execution-ready representation of the template, with resolved concept IDs.

        Raises
        ------
        ValueError
            If the template is missing required semantic components.
        """
        if tpl.entity_concept is None:
            raise ValueError(f"Template {tpl.name} has no entity_concept")

        entity_ids = self.resolver.resolve(tpl.entity_concept)

        value_ids = None
        if tpl.value_concept is not None:
            value_ids = self.resolver.resolve(tpl.value_concept)

        return {
            "name": tpl.name,
            "role": tpl.role,
            "cdm_profile": tpl.cdm_profile,
            "entity_concept_ids": entity_ids,
            "value_concept_ids": value_ids,
        }

@dataclass(frozen=True)
class RuntimeTemplate:
    """
    Attribute-based runtime view over a compiled OMOP template.

    This is a thin wrapper around CompiledTemplate to provide ergonomic
    access in ETL pipelines and execution code.
    """
    name: str
    role: str
    cdm_profile: OmopCdmProfile
    entity_concept_ids: Set[int]
    value_concept_ids: Optional[Set[int]]

    @classmethod
    def from_compiled(cls, c: CompiledTemplate) -> "RuntimeTemplate":
        return cls(
            name=c["name"],
            role=c["role"],
            cdm_profile=c["cdm_profile"],
            entity_concept_ids=c["entity_concept_ids"],
            value_concept_ids=c["value_concept_ids"],
        )


class OmopRegistryRuntime:
    """
    Runtime interface over a registry of OMOP semantic templates.

    This class provides indexed, compiled access to a RegistryFragment,
    allowing templates to be retrieved by name, grouped by role, or
    iterated over in compiled form for use in ETL pipelines and semantic
    execution layers.

    Compilation is cached to avoid repeated semantic resolution and to
    provide stable runtime objects during pipeline execution.
    """

    def __init__(
        self,
        fragment: RegistryFragment,
        template_runtime: OmopTemplateRuntime,
    ):
        """
        Initialise the registry runtime for a semantic registry fragment.

        Parameters
        ----------
        fragment
            Registry fragment containing declarative OMOP semantic templates.
        template_runtime
            Compiler used to convert templates into execution-ready form.
        """
        self.fragment = fragment
        self.template_runtime = template_runtime
        self._compiled_by_name: dict[str, CompiledTemplate] | None = None
        self._compiled_by_role: dict[str, list[CompiledTemplate]] | None = None


    def iter_templates(self, role: str | None = None):
        """
        Iterate over declarative templates in the registry.

        Parameters
        ----------
        role
            Optional semantic role to filter templates (e.g. 'demographic').

        Yields
        ------
        OmopTemplate
            Declarative semantic templates from the registry.
        """
        for group in self.fragment.groups or []:
            for tpl in group.registry_members or []:
                if role is None or tpl.role == role:
                    yield tpl

    def compile_index(self) -> None:
        """
        Compile and index all templates in the registry.

        This method resolves all semantic objects and caches the compiled
        templates for fast lookup by name or role during runtime execution.
        """
        by_name: dict[str, CompiledTemplate] = {}
        by_role: dict[str, list[CompiledTemplate]] = {}

        for tpl in self.iter_templates():
            c = self.template_runtime.compile(tpl)
            by_name[tpl.name] = c
            by_role.setdefault(tpl.role, []).append(c)

        self._compiled_by_name = by_name
        self._compiled_by_role = by_role

    def get(self, name: str) -> CompiledTemplate:
        """
        Retrieve a compiled template by name.

        Parameters
        ----------
        name
            Name of the semantic template.

        Returns
        -------
        CompiledTemplate
            Compiled representation of the named template.

        Raises
        ------
        KeyError
            If no template with the given name exists.
        RuntimeError
            If compilation has failed.
        """
        if self._compiled_by_name is None:
            self.compile_index()
        if self._compiled_by_name is None:
            raise RuntimeError("No compiled templates available")
        return self._compiled_by_name[name]
    
    def get_runtime(self, name: str) -> RuntimeTemplate:
        c = self.get(name)
        return RuntimeTemplate.from_compiled(c)

    def by_role_runtime(self, role: str) -> list[RuntimeTemplate]:
        return [RuntimeTemplate.from_compiled(c) for c in self.by_role(role)]

    def allows_concept(self, template_name: str, concept_id: int) -> bool:
        tpl = self.get(template_name)
        return concept_id in tpl["entity_concept_ids"]

    def allows_value(self, template_name: str, concept_id: int) -> bool:
        tpl = self.get(template_name)
        values = tpl["value_concept_ids"]
        return values is not None and concept_id in values

    def by_role(self, role: str) -> list[CompiledTemplate]:
        """
        Retrieve all compiled templates for a given semantic role.

        Parameters
        ----------
        role
            Semantic role to filter by (e.g. 'demographic', 'staging').

        Returns
        -------
        list[CompiledTemplate]
            List of compiled templates associated with the given role.
        """
        if self._compiled_by_role is None:
            self.compile_index()
        if self._compiled_by_role is None:
            raise RuntimeError("No compiled templates available")
        return self._compiled_by_role.get(role, [])

    def compile_all(self, role: str | None = None) -> list[CompiledTemplate]:
        """
        Retrieve all compiled templates, optionally filtered by role.

        Parameters
        ----------
        role
            Optional semantic role to filter templates.

        Returns
        -------
        list[CompiledTemplate]
            List of compiled templates in the registry.
        """
        if self._compiled_by_name is None:
            self.compile_index()
        if self._compiled_by_name is None:
            raise RuntimeError("Template compilation failed")
        if role is None or self._compiled_by_role is None:
            return list(self._compiled_by_name.values())
        return self._compiled_by_role.get(role, [])
    
    def to_html(self, role: str | None = None) -> Html:
        """
        Render the declarative registry fragment as an HTML table.

        This view displays the semantic templates grouped by registry group,
        showing their role, CDM profile, and associated semantic objects
        (entity and value concepts). It is intended for documentation,
        debugging, and interactive exploration in notebooks.

        Parameters
        ----------
        role
            Optional semantic role to filter templates (e.g. 'demographic', 'staging').
            If provided, only templates with this role are rendered.

        Returns
        -------
        Html
            HTML representation of the registry suitable for display in Jupyter.

        Examples
        --------
        Render the full registry in a notebook:

            >>> engine.registry_runtime.to_html()

        Render only demographic templates:

            >>> engine.registry_runtime.to_html(role="demographic")
        """
        blocks: list[str] = []

        for group in self.fragment.groups or []:
            rows = [
                tr([
                    tpl.name,
                    tpl.role,
                    tpl.cdm_profile.name,
                    render_semantic_object(tpl.entity_concept),
                    render_semantic_object(tpl.value_concept),
                ])
                for tpl in (group.registry_members or [])
                if role is None or tpl.role == role
            ]

            if not rows:
                continue

            blocks.append(
                f"<h3>{h(group.name)} ({h(group.role)})</h3>"
                + table(
                    rows,
                    header=[
                        "Template",
                        "Role",
                        "CDM Profile",
                        "Entity Concept",
                        "Value Concept",
                    ],
                )
                + (f"<p><em>{h(group.notes)}</em></p>" if group.notes else "")
            )

        return Html("".join(blocks))
    
    def _repr_html_(self) -> str:
        """
        Rich HTML representation for interactive notebook display.

        This method delegates to ``to_html()`` so that instances of
        ``OmopRegistryRuntime`` render automatically as HTML when displayed
        in Jupyter or other rich frontends.

        Returns
        -------
        str
            Raw HTML string for rich display.

        Examples
        --------
        In a Jupyter notebook, simply evaluating the object will render
        the registry as HTML:

            >>> engine.registry_runtime
        """
        return self.to_html().raw
    
    def to_compiled_html(self, role: str | None = None) -> Html:
        """
        Render the compiled registry as an HTML table.

        This view displays the execution-ready form of semantic templates,
        where semantic objects have been resolved to concrete OMOP concept IDs.
        It is useful for inspecting the concrete OMOP mappings that will be
        used by ETL pipelines or query builders.

        Parameters
        ----------
        role
            Optional semantic role to filter compiled templates.
            If provided, only compiled templates with this role are rendered.

        Returns
        -------
        Html
            HTML representation of the compiled templates suitable for display
            in Jupyter or documentation.

        Examples
        --------
        Inspect the compiled demographic mappings:

            >>> engine.registry_runtime.to_compiled_html(role="demographic")

        Compare declarative vs compiled views:

            >>> engine.registry_runtime.to_html()
            >>> engine.registry_runtime.to_compiled_html()
        """
        compiled = self.compile_all(role=role)
        return render_compiled_templates(compiled)
    


class SemanticProfileRuntime:
    """
    Runtime interface over semantic profile objects.

    This class provides lightweight, read-only access to profile-layer
    semantic objects (e.g. RegistryGroup, OmopTemplate, OmopGroup, OmopConcept)
    loaded from profile YAML files. It is primarily intended for
    documentation, inspection, and UI / notebook exploration rather than
    execution-time ETL logic.
    """
    def __init__(self, objects: dict[str, dict] | list[dict[str, dict]]):
        """
        Initialise the profile runtime.

        Parameters
        ----------
        objects
            Mapping of profile object names to raw profile dictionaries,
            or a list of such mappings (which will be merged). Later entries
            take precedence when merging.
        """
        if isinstance(objects, list):
            merged: dict[str, dict] = {}
            for obj in objects:
                merged.update(obj)
            objects = merged

        self.objects: dict[str, dict] = objects

    def get(self, name: str) -> dict:
        """
        Retrieve a profile object by name.

        Parameters
        ----------
        name
            Name of the profile object.

        Returns
        -------
        dict
            Raw profile object dictionary.

        Raises
        ------
        KeyError
            If no profile object with the given name exists.
        """
        return self.objects[name]
    
    def list_groups(self) -> dict[str, dict]:
        """
        List all RegistryGroup objects defined in the profiles.

        Returns
        -------
        dict[str, dict]
            Mapping of group name to raw RegistryGroup profile dictionaries.
        """
        return {
            name: obj
            for name, obj in self.objects.items()
            if obj.get("class_uri") == "RegistryGroup"
        }
    
 
    def explain(self, name: str) -> str:
        """
        Return a short human-readable explanation for a profile object.

        This is typically sourced from the ``notes`` field in the profile
        definition and is intended for UI / documentation display.

        Parameters
        ----------
        name
            Name of the profile object.

        Returns
        -------
        str
            Notes or description associated with the object, or a fallback
            message if none is provided.

        Raises
        ------
        KeyError
            If no profile object with the given name exists.
        """
        obj = self.objects[name]
        return obj.get("notes") or f"No notes for {name}"
        
    def _resolve_profile_ref(self, ref: object) -> dict:
        """
        Resolve a profile reference which may be:
        - a string key into self.objects
        - an inline dict
        - None / missing

        Always returns a dict suitable for render_profile_object.
        """
        if isinstance(ref, str):
            obj = self.objects.get(ref)
            return obj if isinstance(obj, dict) else {}
        if isinstance(ref, dict):
            return ref
        return {}

    
    def to_html(self) -> Html:
        """
        Render all loaded semantic profile objects as HTML documentation.

        This produces a lightweight, human-readable overview of:
        - Registry groups
        - Templates
        - Semantic objects (groups, concepts, enums)

        Returns
        -------
        Html
            Rendered HTML block suitable for notebook display.
        """
        blocks: list[str] = []

        # ---- Registry Groups ----
        group_rows = [
            tr([
                name,
                obj.get("role", ""),
                ", ".join(as_list(obj.get("members"))),
                obj.get("notes", ""),
            ])
            for name, obj in self.objects.items()
            if obj.get("class_uri") == "RegistryGroup"
        ]

        if group_rows:
            blocks.append(
                "<h3>Registry Groups</h3>"
                + table(
                    group_rows,
                    header=["Name", "Role", "Members", "Notes"],
                )
            )

        template_rows = [
            tr([
                name,
                obj.get("role", ""),
                obj.get("cdm_profile", ""),
                render_profile_object(self._resolve_profile_ref(obj.get("entity_concept"))),
                render_profile_object(self._resolve_profile_ref(obj.get("value_concept"))),
            ])
            for name, obj in self.objects.items()
            if obj.get("class_uri") == "OmopTemplate"
        ]

        if template_rows:
            blocks.append(
                "<h3>Templates</h3>"
                + table(
                    template_rows,
                    header=[
                        "Name",
                        "Role",
                        "CDM Profile",
                        "Entity Concept",
                        "Value Concept",
                    ],
                )
            )

        semantic_rows = [
            tr([
                name,
                obj.get("class_uri"),
                render_profile_object(obj),
                obj.get("notes", ""),
            ])
            for name, obj in self.objects.items()
            if obj.get("class_uri") in {"OmopGroup", "OmopConcept", "OmopEnum"}
        ]

        if semantic_rows:
            blocks.append(
                "<h3>Semantic Objects</h3>"
                + table(
                    semantic_rows,
                    header=["Name", "Type", "Details", "Notes"],
                )
            )

        return Html("".join(blocks))


    def _repr_html_(self) -> str:
        """
        Jupyter/IPython rich display hook.
        """
        return self.to_html().raw


    def explain_html(self, name: str) -> Html:
        """
        Render a single profile object as a simple key/value HTML table.

        Parameters
        ----------
        name
            Name of the profile object to explain.

        Returns
        -------
        Html
            Rendered HTML block showing all fields on the object.
        """
        obj = self.objects[name]

        rows = [
            tr([k, v])
            for k, v in obj.items()
        ]

        return Html(
            f"<h3>{h(name)}</h3>"
            + table(rows, header=["Field", "Value"])
        )


class OmopSemanticEngine:
    """
    High-level entry point for working with OMOP semantic registries and profiles.

    This class wires together:
      - the semantic resolver (concept/group/enum → OMOP concept_ids),
      - the template compiler runtime,
      - the registry runtime (indexed, compiled templates),
      - and the optional semantic profile runtime (symbolic/profile view).

    It is intended to be the main object used by ETL pipelines, query builders,
    and documentation/rendering layers.
    """

    def __init__(
        self,
        registry_fragment: RegistryFragment,
        profile_objects: dict[str, dict] | None = None,
    ):
        """
        Construct a semantic engine from an already-loaded registry fragment.

        Parameters
        ----------
        registry_fragment
            Declarative registry fragment defining OMOP semantic templates and groups.
        profile_objects
            Optional mapping of symbolic profile objects (e.g. OmopTemplate, OmopGroup,
            OmopConcept definitions) used for documentation and inspection.
        """
        self.resolver = OmopSemanticResolver()
        self.template_runtime = OmopTemplateRuntime(self.resolver)
        self.registry_runtime = OmopRegistryRuntime(
            fragment=registry_fragment,
            template_runtime=self.template_runtime,
        )
        self.profile_runtime = (
            SemanticProfileRuntime(profile_objects)
            if profile_objects is not None
            else None
        )

    @classmethod
    def from_instances(cls, fragment: RegistryFragment) -> "OmopSemanticEngine":
        """
        Construct a semantic engine directly from an in-memory RegistryFragment.

        This is useful in tests or programmatic composition of registry fragments.

        Parameters
        ----------
        fragment
            Registry fragment containing semantic templates.

        Returns
        -------
        OmopSemanticEngine
            Initialised semantic engine.
        """
        return cls(registry_fragment=fragment)

    @classmethod
    def from_yaml_paths(
        cls,
        registry_paths: Iterable[Path],
        profile_paths: Iterable[Path] = (),
    ) -> "OmopSemanticEngine":
        """
        Construct a semantic engine from YAML registry and profile files.

        Multiple registry fragments are merged into a single runtime registry.
        Profile YAML files are loaded and merged into a single symbolic profile
        namespace for documentation and inspection.

        Parameters
        ----------
        registry_paths
            Paths to registry fragment YAML files.
        profile_paths
            Optional paths to profile/symbol YAML files.

        Returns
        -------
        OmopSemanticEngine
            Initialised semantic engine with merged registry and profiles.
        """
        fragments: list[RegistryFragment] = []
        profile_objects: dict[str, dict] = {}

        for p in registry_paths:
            fragments.append(load_registry_fragment(p))

        for p in profile_paths:
            profile_objects.update(load_symbol_module(p))

        merged_fragment = merge_registry_fragments(fragments)

        return cls(
            registry_fragment=merged_fragment,
            profile_objects=profile_objects or None,
        )

    def docs_html(self) -> Html:
        """
        Render combined HTML documentation for the registry and profiles.

        Returns
        -------
        Html
            HTML block containing registry tables and (if available) profile
            documentation.
        """
        parts = [
            "<h2>Registry</h2>",
            self.registry_runtime.to_html().raw,
        ]

        if self.profile_runtime is not None:
            parts.extend([
                "<h2>Profiles</h2>",
                self.profile_runtime.to_html().raw,
            ])

        return Html("".join(parts))
