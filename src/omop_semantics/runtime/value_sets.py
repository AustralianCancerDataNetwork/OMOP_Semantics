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

from .renderers import tr, table, h, Html

class RuntimeGroup:
    def __init__(self, group: OmopGroup):
        self._group = group
        self._by_label = {
            c.label: c.concept_id
            for c in (group.parent_concepts or [])
            if c and c.label and c.concept_id
        }

    def __getattr__(self, label: str) -> int:
        if label.startswith("_"):
            raise AttributeError(label)
        return self._by_label[label]

    def __repr__(self) -> str:
        labels = ", ".join(sorted(self._by_label.keys()))
        return f"RuntimeGroup({self._group.name}: [{labels}])"

    def _repr_html_(self) -> str:
        rows = [
            tr([label, cid])
            for label, cid in sorted(self._by_label.items())
        ]
        return Html(
            f"<h4>Group: {h(self._group.name)}</h4>"
            + table(rows, header=["Label", "Concept ID"])
        ).raw

    def __dir__(self):
        return sorted(set(super().__dir__()) | set(self._by_label.keys()))

class RuntimeEnum:

    def __init__(self, enum: OmopEnum):
        self._enum = enum
        self._by_label = {m.label: m.concept_id for m in enum.enum_members if m.concept_id and m.label}

    def __getattr__(self, label: str) -> int:
        if label.startswith('_'):
            raise AttributeError(label)
        return self._by_label[label]
    
    def __repr__(self) -> str:
        labels = ", ".join(sorted(self._by_label.keys()))
        return f"RuntimeEnum({self._enum.name}: [{labels}])"

    def _repr_html_(self) -> str:
        rows = [
            tr([label, cid])
            for label, cid in sorted(self._by_label.items())
        ]
        return Html(
            f"<h4>Enum: {h(self._enum.name)}</h4>"
            + table(rows, header=["Label", "Concept ID"])
        ).raw
    

    def __dir__(self):
        return sorted(set(super().__dir__()) | set(self._by_label.keys()))


class RuntimeSemanticUnit:
    def __init__(self, unit: CDMSemanticUnits):
        self._unit = unit
        self.enums = {e.name: RuntimeEnum(e) for e in (unit.named_enumerators or []) if e and e.name}
        self.groups = {g.name: RuntimeGroup(g) for g in (unit.named_groups or []) if g and g.name}        
        self.concepts = {c.name: c for c in (unit.named_concepts or []) if c and c.name}


    def __getattr__(self, name: str):
        if name in self.enums:
            return self.enums[name]
        if name in self.groups:
            return self.groups[name]
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
    name: str
    members: dict[str, RuntimeSemanticUnit]

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
    Flatten CDMSemanticUnits into name → OmopSemanticObject mapping.
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
