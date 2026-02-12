from dataclasses import dataclass
from omop_semantics.schema.generated_models.omop_named_sets import (
    OmopConcept, 
    OmopGroup, 
    OmopEnum, 
    OmopSemanticObject, 
    CDMSemanticUnits,
    CDMValueSet,
    CDMValueSets
)
from abc import ABC
from .renderers import tr, table, h, Html

"""
Runtime accessors for OMOP semantic value sets.

This module provides a lightweight, interactive runtime layer over declarative
OMOP semantic registries defined using LinkML schemas and YAML instance files.
It exposes semantic enums, groups, and concepts as Python attribute-accessible
namespaces, with rich ``repr`` and ``_repr_html_`` renderings for notebook
exploration.

The runtime API is designed for:

- Interactive exploration of available semantic objects in Jupyter
- Readable rule logic (e.g. ``runtime.genomic.genomic_value_group.genomic_positive``)
- Debugging and documentation of registry content
- Safe programmatic access to OMOP concept identifiers

The core abstractions are:

- ``RuntimeEnum``: wraps an ``OmopEnum`` as a label-concept_id namespace
- ``RuntimeGroup``: wraps an ``OmopGroup`` as a label-concept_id namespace
- ``RuntimeSemanticUnit``: aggregates enums, groups, and concepts under one unit
- ``RuntimeValueSet``: groups semantic units into named value sets
- ``RuntimeValueSets``: top-level registry namespace

This layer intentionally avoids mutability and database concerns and is intended
as a pure read-only semantic access layer.
"""

from abc import ABC
from typing import Mapping

class _RuntimeLabelledConcepts(ABC):
    """
    Thin shared base for runtime objects that expose a label -> concept_id mapping.
    """

    _by_label: Mapping[str, int]
    _name: str

    kind_label: str = "Concepts"   # overridden in subclasses
    kind_tag: str = "RuntimeConcepts"

    @property
    def labels(self) -> list[str]:
        return sorted(self._by_label.keys())

    @property
    def ids(self) -> set[int]:
        return set(self._by_label.values())

    def mapper(self) -> dict[str, int]:
        return dict(self._by_label)

    def __getattr__(self, label: str) -> int:
        if label.startswith("_"):
            raise AttributeError(label)
        return self._by_label[label]

    def __repr__(self) -> str:
        labels = ", ".join(self.labels)
        return f"{self.kind_tag}({self._name}: [{labels}])"

    def _repr_html_(self) -> str:
        rows = [tr([label, cid]) for label, cid in sorted(self._by_label.items())]
        return Html(
            f"<h4>{h(self.kind_label)}: {h(self._name)}</h4>"
            + table(rows, header=["Label", "Concept ID"])
        ).raw

class RuntimeGroup(_RuntimeLabelledConcepts):
    """
    Runtime wrapper around an ``OmopGroup``.

    Exposes the group's parent concepts as an attribute-accessible namespace,
    mapping concept labels to OMOP concept IDs. This allows interactive access
    such as:

        >>> runtime.staging.t_stage_concepts.t3
        1634376

    """

    kind_label = "Group"
    kind_tag = "RuntimeGroup"

    def __init__(self, group: OmopGroup):
        self._group = group
        self._name = group.name or '[group]'
        self._by_label = {
            c.label: c.concept_id
            for c in (group.parent_concepts or [])
            if c and c.label and c.concept_id
        }

    @property
    def is_singleton(self) -> bool:
        return len(self._by_label) == 1
    
    @property
    def value(self) -> int:
        """
        Return the sole concept_id if this group has exactly one parent.
        """
        if not self.is_singleton:
            raise AttributeError(
                f"Group '{self._group.name}' has multiple parent concepts"
            )
        return next(iter(self._by_label.values()))
    
    def __int__(self) -> int:
        """
        Allow int(runtime.group) for singleton groups.
        """
        return self.value

class RuntimeEnum(_RuntimeLabelledConcepts):

    """
    Runtime wrapper around an ``OmopEnum``.

    Exposes enum members as a label to concept_id mapping, accessible via
    attribute access:

        >>> runtime.genomic.genomic_value_group.genomic_positive
        9191

    Attributes
    ----------
    labels : list[str]
        Sorted list of enum labels.
    ids : list[int]
        Sorted list of concept IDs in the enum.

    """

    kind_label = "Enum"
    kind_tag = "RuntimeEnum"

    def __init__(self, enum: OmopEnum):
        self._enum = enum
        self._name = enum.name or '[enum]'
        self._by_label = {
            m.label: m.concept_id
            for m in enum.enum_members
            if m.concept_id and m.label
        }
        

class RuntimeConcept:
    def __init__(self, concept: OmopConcept):
        self._concept = concept

    @property
    def value(self) -> int | None:
        return self._concept.concept_id

    @property
    def values(self) -> set[int]:
        return {self.value if self.value else 0}

class RuntimeSemanticUnit:

    """
    Runtime container for a single semantic unit.

    A semantic unit may contain any combination of:

    - Named enums (``RuntimeEnum``)
    - Named groups (``RuntimeGroup``)
    - Named concepts (raw ``OmopConcept``)

    This class exposes:

    - Direct access to named enums/groups/concepts via attributes
    - Direct access to enum/group labels as attributes (flattened lookup)
    - Rich textual and HTML representations for introspection

    Example
    -------
        >>> runtime.genomic.genomic_value_group.genomic_positive
        9191

        >>> runtime.staging.t_stage_concepts.t4
        1634654
    """

    def __init__(self, unit: CDMSemanticUnits):
        self._unit = unit
        self.enums = {e.name: RuntimeEnum(e) for e in (unit.named_enumerators or []) if e and e.name}
        self.groups = {g.name: RuntimeGroup(g) for g in (unit.named_groups or []) if g and g.name}        
        self.concepts = {c.name: c for c in (unit.named_concepts or []) if c and c.name}

    @property
    def ids(self) -> set[int]:
        vals: set[int] = set()

        for enum in self.enums.values():
            vals |= enum.ids

        for group in self.groups.values():
            vals |= group.ids

        for concept in self.concepts.values():
            if concept and concept.concept_id:
                vals.add(concept.concept_id)

        return vals

    def __getattr__(self, name: str):
        if name in self.enums:
            return self.enums[name]
        if name in self.groups:
            g = self.groups[name]
            if g.is_singleton:
                return g.value
            return g
        if name in self.concepts:
            return self.concepts[name]

        for labelled_item in [self.enums, self.groups]:
            for value in labelled_item.values():
                try:
                    return getattr(value, name)
                except AttributeError:
                    pass

        raise AttributeError(name)

    def __repr__(self) -> str:
        parts = []
        if self.enums:
            parts.append(f"enums={list(self.enums.keys())}")
        if self.groups:
            parts.append(f"groups={list(self.groups.keys())}")
        if self.concepts:
            parts.append(f"concepts={list(self.concepts.keys())}")

        inner = ", ".join(parts) if parts else "empty"
        return f"RuntimeSemanticUnit({self._unit.name}: {inner})"

    def _repr_html_(self) -> str:
        rows = []
        for name in sorted(self.enums):
            rows.append(tr(["Enum", name, ", ".join(self.enums[name]._by_label.keys())]))
        for name, g in sorted(self.groups.items()):
            if g._group.parent_concepts:
                rows.append(tr(["Group", name, ", ".join(c.label for c in g._group.parent_concepts if c and c.label)]))
        for name in sorted(self.concepts):
            rows.append(tr(["Concept", name, ""]))

        return Html(
            f"<h3>Semantic Unit: {h(self._unit.name)}</h3>"
            + table(rows, header=["Type", "Name", "Members"])
        ).raw
    
    def __dir__(self):
        names = set(self.enums) | set(self.groups) | set(self.concepts)

        for enum in self.enums.values():
            names |= set(enum._by_label.keys())

        for group in self.groups.values():
            names |= set(group._by_label.keys())

        return sorted(set(super().__dir__()) | names)

@dataclass(frozen=True)
class RuntimeValueSet:

    """
    Runtime representation of a named value set.

    A value set groups multiple semantic units under a single namespace or 
    conceptual module - no added functionality just for ease of access and use

    (e.g. ``genomic``, ``staging``, ``modifiers``).

    Semantic units can be accessed via attribute lookup:

        >>> runtime.genomic.genomic_value_group
        RuntimeSemanticUnit(...)

    """

    name: str
    members: dict[str, RuntimeSemanticUnit]


    @property
    def ids(self) -> set[int]:
        vals: set[int] = set()
        for vs in self.members.values():
            vals |= vs.ids
        return vals

    def __getattr__(self, name: str) -> RuntimeSemanticUnit:
        try:
            return self.members[name]
        except KeyError:
            raise AttributeError(name)
        
    def __repr__(self) -> str:
        keys = ", ".join(sorted(self.members.keys()))
        return f"RuntimeValueSet({self.name}: [{keys}])"

    def _repr_html_(self) -> str:
        rows = [
            tr([name, 
                ", ".join(unit.enums.keys()),
                ", ".join(unit.groups.keys()),
                ", ".join(unit.concepts.keys())])
            for name, unit in sorted(self.members.items())
        ]

        return Html(
            f"<h2>ValueSet: {h(self.name)}</h2>"
            + table(rows, header=["Semantic Unit", "Enums", "Groups", "Concepts"])
        ).raw
    
    def __dir__(self):
        return sorted(set(super().__dir__()) | set(self.members.keys()))
    

class RuntimeValueSets:

    """
    Top-level runtime namespace for all compiled value sets.

    This is the primary entry point for interactive access to the semantic
    registry:

        >>> runtime.genomic
        >>> runtime.staging
        >>> runtime.nlp

    Each attribute corresponds to a named ``RuntimeValueSet``.

    """

    def __init__(self, valuesets: dict[str, RuntimeValueSet]):
        self._valuesets = valuesets

    def __getattr__(self, name: str) -> RuntimeValueSet:
        if name.startswith('_'):
            raise AttributeError(name)
        return self._valuesets[name]

    def __repr__(self) -> str:
        keys = ", ".join(sorted(self._valuesets.keys()))
        return f"RuntimeValueSets([{keys}])"

    def _repr_html_(self) -> str:
        
        rows = [
            tr([name, ", ".join(sorted(vs.members.keys()))])
            for name, vs in sorted(self._valuesets.items())
        ]

        return Html(
            "<h1>OMOP Semantic Registry</h1>"
            + table(rows, header=["ValueSet", "Semantic Units"])
        ).raw
    
    def __dir__(self):
        return sorted(set(super().__dir__()) | set(self._valuesets.keys()))
    
  
def compile_valuesets(defs: CDMValueSets) -> RuntimeValueSets:

    """
    Compile declarative CDM value set definitions into runtime objects.

    Parameters
    ----------
    defs : CDMValueSets
        Parsed value set definitions after interpolation.

    Returns
    -------
    RuntimeValueSets
        Runtime-accessible registry of all value sets and semantic units.

    Notes
    -----
    This step materialises the interactive runtime namespace used in notebooks
    and rule logic. It is intentionally pure and read-only.
    """

    compiled: dict[str, RuntimeValueSet] = {}

    for vs in defs.valuesets:
        members = {
            (unit.name or "[unlabelled]"): RuntimeSemanticUnit(unit)
            for unit in vs.members
        }

        compiled[vs.valueset_name] = RuntimeValueSet(
            name=vs.valueset_name,
            members=members,
        )

    return RuntimeValueSets(compiled)


def index_semantic_units(units: CDMSemanticUnits) -> dict[str, OmopSemanticObject]:
    """
    Build a name → semantic object index from a ``CDMSemanticUnits`` container.

    Parameters
    ----------
    units : CDMSemanticUnits
        Declarative semantic unit registry.

    Returns
    -------
    dict[str, OmopSemanticObject]
        Mapping from semantic unit name to underlying OMOP semantic object
        (enum, group, or concept).

    This index is used during interpolation of value set definitions.
    """

    index: dict[str, OmopSemanticObject] = {}

    for e in units.named_enumerators or []:
        if e.name:
            index[e.name] = e

    for g in units.named_groups or []:
        if g.name:
            index[g.name] = g

    for c in units.named_concepts or []:
        if c.name:
            index[c.name] = c

    return index

def interpolate_valuesets(
    raw: dict,
    semantic_index: dict[str, OmopSemanticObject],
) -> CDMValueSets:
    """
    Interpolate raw value set definitions by resolving string references.

    This replaces string references in ``valuesets.yaml`` with concrete
    ``CDMSemanticUnits`` instances wrapping the corresponding OMOP semantic
    objects.

    Parameters
    ----------
    raw : dict
        Raw parsed YAML dictionary from ``valuesets.yaml``.
    semantic_index : dict[str, OmopSemanticObject]
        Lookup table mapping semantic unit names to OMOP semantic objects.

    Returns
    -------
    CDMValueSets
        Fully resolved value set definitions suitable for compilation into
        runtime objects.

    Raises
    ------
    KeyError
        If a referenced semantic unit name does not exist.
    TypeError
        If an unsupported semantic object type is encountered.
    """
    valuesets = []

    for vs in raw["valuesets"]:
        resolved_members: list[CDMSemanticUnits] = []

        for name in vs["members"]:
            if name not in semantic_index:
                raise KeyError(f"Unknown semantic unit referenced in valuesets.yaml: {name}")

            obj = semantic_index[name]

            named_enums = []
            named_groups = []
            named_concepts = []

            if isinstance(obj, OmopEnum):
                named_enums = [obj]
            elif isinstance(obj, OmopGroup):
                named_groups = [obj]
            elif isinstance(obj, OmopConcept):
                named_concepts = [obj]
            else:
                raise TypeError(f"Unsupported semantic unit type: {type(obj)}")

            resolved_members.append(
                CDMSemanticUnits(
                    name=name,
                    named_enumerators=named_enums,
                    named_groups=named_groups,
                    named_concepts=named_concepts,
                )
            )

        valuesets.append(
            CDMValueSet(
                valueset_name=vs["name"],
                members=resolved_members,
            )
        )

    return CDMValueSets(valuesets=valuesets)
