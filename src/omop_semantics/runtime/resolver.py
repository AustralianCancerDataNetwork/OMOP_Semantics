from omop_semantics.schema.generated_models.omop_semantic_registry import (
    OmopConcept, 
    OmopGroup, 
    OmopEnum, 
    RegistryFragment, 
    OmopSemanticObject, 
    OmopTemplate,
    RegistryGroup,
    OmopCdmProfile
)
from linkml_runtime.loaders import yaml_loader
from pathlib import Path
from typing import Iterable, Sequence
from .renderers import render_semantic_object, render_profile_object, Html, tr, h, table, as_list
from .instance_loader import load_registry_fragment, merge_instance_files, merge_registry_fragments, load_profiles

class OmopSemanticResolver:
    
    def resolve(self, obj: OmopSemanticObject) -> set[int]:
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
    def __init__(self, resolver: OmopSemanticResolver):
        self.resolver = resolver

    def compile(self, tpl: OmopTemplate) -> dict:
        if tpl.entity_concept is None:
            raise ValueError(f"Template {tpl.name} has no entity_concept")

        entity_ids = self.resolver.resolve(tpl.entity_concept)

        value_ids = None
        if tpl.value_concept is not None:
            value_ids = self.resolver.resolve(tpl.value_concept)

        return {
            "name": tpl.name,
            "cdm_profile": tpl.cdm_profile,
            "entity_concept_ids": entity_ids,
            "value_concept_ids": value_ids,
        }

class OmopRegistryRuntime:
    def __init__(
        self,
        fragment: RegistryFragment,
        template_runtime: OmopTemplateRuntime,
    ):
        self.fragment = fragment
        self.template_runtime = template_runtime

    def iter_templates(self, role: str | None = None):
        for group in self.fragment.groups or []:
            for tpl in group.registry_members or []:
                if role is None or tpl.role == role:
                    yield tpl

    def compile_all(self, role: str | None = None) -> list[dict]:
        return [
            self.template_runtime.compile(tpl)
            for tpl in self.iter_templates(role=role)
        ]

    def by_group(self) -> dict[str, list[OmopTemplate]]:
        return {
            group.name: list(group.registry_members or [])
            for group in self.fragment.groups or []
        }
    
    def to_html(self, role: str | None = None) -> Html:
        blocks = []

        for group in self.fragment.groups or []:
            rows = []
            for tpl in group.registry_members or []:
                if role is not None and tpl.role != role:
                    continue

                rows.append(tr([
                    tpl.name,
                    tpl.role,
                    tpl.cdm_profile,
                    render_semantic_object(tpl.entity_concept),
                    render_semantic_object(tpl.value_concept),
                ]))

            if not rows:
                continue

            html = table(
                rows,
                header=[
                    "Template",
                    "Role",
                    "CDM Profile",
                    "Entity Concept",
                    "Value Concept",
                ],
            )

            blocks.append(
                f"<h3>{h(group.name)} ({h(group.role)})</h3>"
                f"{html}"
                + (f"<p><em>{h(group.notes)}</em></p>" if group.notes else "")
            )

        return Html("".join(blocks))
    
    def _repr_html_(self) -> str:
        return self.to_html().raw
    

    def to_compiled_html(self, role: str | None = None) -> Html:
        compiled = self.compile_all(role=role)

        rows = []
        for c in compiled:
            rows.append(tr([
                c["name"],
                c["cdm_profile"],
                ", ".join(map(str, sorted(c["entity_concept_ids"]))),
                ", ".join(map(str, sorted(c["value_concept_ids"] or []))),
            ]))

        return Html(table(
            rows,
            header=[
                "Template",
                "CDM Profile",
                "Entity Concept IDs",
                "Value Concept IDs",
            ],
        ))

class SemanticProfileRuntime:
    def __init__(self, objects: dict[str, dict]):
        self.objects = objects

    def get(self, name: str) -> dict:
        return self.objects[name]

    def list_groups(self):
        return {
            k: v for k, v in self.objects.items()
            if v.get("class_uri") == "RegistryGroup"
        }

    def explain(self, name: str) -> str:
        obj = self.objects[name]
        return obj.get("notes") or f"No notes for {name}"

    def to_html(self) -> Html:
        blocks = []

        # ---- Registry Groups ----
        group_rows = []
        for name, obj in self.objects.items():
            if obj.get("class_uri") == "RegistryGroup":
                group_rows.append(tr([
                    name,
                    obj.get("role", ""),
                    ", ".join(as_list(obj.get("members"))),
                    obj.get("notes", ""),
                ]))

        if group_rows:
            blocks.append(
                "<h3>Registry Groups</h3>"
                + table(
                    group_rows,
                    header=["Name", "Role", "Members", "Notes"],
                )
            )

        template_rows = []
        for name, obj in self.objects.items():
            if obj.get("class_uri") == "OmopTemplate":
                template_rows.append(tr([
                    name,
                    obj.get("role", ""),
                    obj.get("cdm_table", ""),
                    obj.get("concept_slot", ""),
                    obj.get("value_slot", ""),
                    render_profile_object(self.objects.get(obj.get("entity_concept"), {}))
                    if isinstance(obj.get("entity_concept"), str)
                    else render_profile_object(obj.get("entity_concept", {})),
                    render_profile_object(self.objects.get(obj.get("value_concept"), {}))
                    if isinstance(obj.get("value_concept"), str)
                    else render_profile_object(obj.get("value_concept", {})),
                ]))

        if template_rows:
            blocks.append(
                "<h3>Templates</h3>"
                + table(
                    template_rows,
                    header=[
                        "Name",
                        "Role",
                        "CDM Table",
                        "Concept Slot",
                        "Value Slot",
                        "Entity Concept",
                        "Value Concept",
                    ],
                )
            )

        semantic_rows = []
        for name, obj in self.objects.items():
            if obj.get("class_uri") in {"OmopGroup", "OmopConcept", "OmopEnum"}:
                semantic_rows.append(tr([
                    name,
                    obj.get("class_uri"),
                    render_profile_object(obj),
                    obj.get("notes", ""),
                ]))

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
        return self.to_html().raw

    def explain_html(self, name: str) -> Html:
        obj = self.objects[name]

        rows = []
        for k, v in obj.items():
            rows.append(tr([k, v]))

        return Html(
            f"<h3>{h(name)}</h3>"
            + table(rows, header=["Field", "Value"])
        )



class OmopSemanticEngine:
    def __init__(
        self,
        registry_fragment: RegistryFragment,
        profile_objects: dict[str, dict] | None = None,
    ):
        self.resolver = OmopSemanticResolver()
        self.template_runtime = OmopTemplateRuntime(self.resolver)
        self.registry_runtime = OmopRegistryRuntime(
            registry_fragment,
            self.template_runtime,
        )
        self.profile_runtime = (
            SemanticProfileRuntime(profile_objects)
            if profile_objects is not None
            else None
        )

    @classmethod
    def from_instances(
        cls,
        fragment: RegistryFragment
    ):
        return cls(
            registry_fragment=fragment
        )

    @classmethod
    def from_yaml_paths(
        cls,
        registry_paths: Iterable[Path],
        profile_paths: Iterable[Path] = (),
    ) -> "OmopSemanticEngine":
        fragments: list[RegistryFragment] = []
        profile_objects: dict[str, OmopCdmProfile] = {}

        for p in registry_paths:
            frag = load_registry_fragment(p)
            fragments.append(frag)

        for p in profile_paths:
            profile_objects.update(load_profiles(p))

        merged_fragment = merge_registry_fragments(fragments)

        return cls(
            registry_fragment=merged_fragment,
            profile_objects=profile_objects or None,
        )
    

    def docs_html(self) -> Html:
        parts = [
            "<h2>Registry</h2>",
            self.registry_runtime.to_html().raw,
        ]
        if self.profile_runtime:
            parts += [
                "<h2>Profiles</h2>",
                self.profile_runtime.to_html().raw,
            ]
        return Html("".join(parts))
