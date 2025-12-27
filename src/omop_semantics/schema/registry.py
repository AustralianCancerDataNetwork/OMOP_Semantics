
from dataclasses import dataclass, replace
from typing import Optional, Tuple, Iterable, Iterator, Mapping, Protocol, runtime_checkable, Any
from collections import defaultdict
from .schema_model import SchemaInfo

@dataclass(frozen=True)
class ConceptRecord:
    concept_id: int
    label: str
    role: str
    parents: Tuple[int, ...] = ()
    notes: Optional[str] = None

@dataclass(frozen=True)
class ConceptGroupRecord:
    name: str
    role: str
    members: tuple[int, ...]
    notes: Optional[str] = None

@runtime_checkable
class SupportsConceptRegistry(Protocol):
    def get(self, concept_id: int) -> ConceptRecord: ...
    def try_get(self, concept_id: int) -> Optional[ConceptRecord]: ...
    def by_role(self, role: str) -> set[int]: ...
    def parents_of(self, concept_id: int) -> tuple[int, ...]: ...
    def ancestors_of(self, concept_id: int) -> tuple[int, ...]: ...


class ConceptRegistry:
    """
    Runtime registry of OMOP semantic concepts loaded from LinkML instances.
    """

    def __init__(
        self,
        *,
        concepts: Iterable[ConceptRecord],
        groups: Iterable[ConceptGroupRecord],
        schema: SchemaInfo | None = None,
    ):
        self._concepts: dict[int, ConceptRecord] = {}
        self._groups: dict[str, ConceptGroupRecord] = {}
        self._schema = schema
        self._by_role: dict[str, set[int]] = defaultdict(set)
        self._by_label: dict[str, int] = {}
        self._groups_by_member: dict[int, set[str]] = defaultdict(set)

        for g in groups:
            self._groups[g.name.lower()] = g
            for cid in g.members:
                self._groups_by_member[cid].add(g.name)

        for c in concepts:
            self._concepts[c.concept_id] = c
            self._by_role[c.role].add(c.concept_id)
            self._by_label[c.label.lower()] = c.concept_id

        self._ancestor_cache: dict[int, tuple[int, ...]] = {}


    @property
    def schema(self) -> SchemaInfo | None:
        return self._schema

    def get(self, concept_id: int) -> ConceptRecord:
        return self._concepts[concept_id]

    def try_get(self, concept_id: int) -> Optional[ConceptRecord]:
        return self._concepts.get(concept_id)

    def has(self, concept_id: int) -> bool:
        return concept_id in self._concepts

    def concepts(self) -> Iterator[ConceptRecord]:
        return iter(self._concepts.values())

    def groups(self) -> Iterator[ConceptGroupRecord]:
        return iter(self._groups.values())


    def roles(self) -> tuple[str, ...]:
        """
        Known roles in this registry. If schema is present, return schema roles
        (stable ordering). Otherwise return roles seen in instance data.
        """
        if self._schema:
            return tuple(sorted(self._schema.roles.keys()))
        return tuple(sorted(self._by_role.keys()))

    def describe_role(self, role: str) -> str:
        if self._schema and role in self._schema.roles:
            return self._schema.roles[role].description or ""
        return ""

    def classes(self) -> tuple[str, ...]:
        if not self._schema:
            return ()
        return tuple(sorted(self._schema.classes))

    def by_role(self, role: str) -> set[int]:
        return self._by_role.get(role, set())

    def is_role(self, concept_id: int, role: str) -> bool:
        return concept_id in self._by_role.get(role, ())

    def unknowns(self) -> set[int]:
        return self._by_role.get("unknown", set())

    def is_unknown(self, concept_id: Optional[int]) -> bool:
        return (
            concept_id is None
            or concept_id in self._by_role.get("unknown", ())
        )

    def default_unknown(self, label_hint: str = "default unknown") -> int:
        """
        Retrieve a default unknown concept by label hint.
        Falls back to generic unknown.
        """
        key = label_hint.lower()
        if key in self._by_label:
            cid = self._by_label[key]
            if self.is_unknown(cid):
                return cid

        # fallback
        unk = sorted(self.unknowns())
        if unk:
            return unk[0]
        
        raise KeyError("No unknown concepts registered")

    def group(self, name: str) -> ConceptGroupRecord:
        return self._groups[name.lower()]
    
    def groups_for(self, concept_id: int) -> set[str]:
        return self._groups_by_member.get(concept_id, set())

    def try_group(self, name: str) -> ConceptGroupRecord | None:
        return self._groups.get(name.lower())

    def group_members(self, name: str) -> tuple[int, ...]:
        return self.group(name).members

    def parents_of(self, concept_id: int) -> tuple[int, ...]:
        return self.get(concept_id).parents
    
    def in_group(self, concept_id: int, group: str) -> bool:
        return concept_id in self._groups_by_member and group in self._groups_by_member[concept_id]

    def groups_by_role(self, role: str) -> dict[str, ConceptGroupRecord]:
        return {
            name: group
            for name, group in self._groups.items()
            if group.role == role
        }

    def ancestors_of(self, concept_id: int) -> tuple[int, ...]:
        """
        Semantic ancestors via ConceptRecord.parents, not OMOP concept_ancestor.
        Cached per registry instance.
        """
        if concept_id in self._ancestor_cache:
            return self._ancestor_cache[concept_id]

        seen: set[int] = set()
        stack = list(self.parents_of(concept_id))

        while stack:
            pid = stack.pop()
            if pid in seen:
                continue
            seen.add(pid)
            rec = self.try_get(pid)
            if rec:
                stack.extend(rec.parents)

        out = tuple(sorted(seen))
        self._ancestor_cache[concept_id] = out
        return out

    def descendants_of(self, concept_id: int) -> tuple[int, ...]:
        """
        Inverse semantic traversal (O(n) scan). Fine for your scale.
        """
        out = []
        for c in self._concepts.values():
            if concept_id in c.parents:
                out.append(c.concept_id)
        return tuple(sorted(out))


    def validate(
        self,
        *,
        strict_roles: bool = True,
        strict_parents: bool = True,
        strict_group_members: bool = True,
        strict_schema_classes: bool = False,
    ) -> None:
        """
        Validate registry integrity using schema semantics.

        - strict_roles: concept.role must exist in schema roles (if schema loaded)
        - strict_parents: all parent ids must exist as concepts
        - strict_group_members: group members must exist as concepts
        - strict_schema_classes: if you're emitting/round-tripping, ensure schema
          contains expected classes ("OmopConcept", "ConceptGroup")
        """
        if self._schema:
            if strict_schema_classes:
                missing = {"OmopConcept", "ConceptGroup"} - self._schema.classes
                if missing:
                    raise ValueError(f"Schema missing required classes: {sorted(missing)}")

        # roles
        if strict_roles and self._schema:
            for c in self._concepts.values():
                if c.role not in self._schema.roles:
                    raise ValueError(f"Unknown role '{c.role}' for concept {c.concept_id}")

            for g in self._groups.values():
                if g.role not in self._schema.roles:
                    raise ValueError(f"Unknown role '{g.role}' for group {g.name}")

        # parents
        if strict_parents:
            for c in self._concepts.values():
                for pid in c.parents:
                    if pid not in self._concepts:
                        raise ValueError(
                            f"Concept {c.concept_id} has parent {pid} not present in registry"
                        )

            # cycle detection (semantic parents)
            self._validate_no_parent_cycles()

        # group members
        if strict_group_members:
            for g in self._groups.values():
                for mid in g.members:
                    if mid not in self._concepts:
                        raise ValueError(
                            f"Group '{g.name}' references member {mid} not present in registry"
                        )

    def _validate_no_parent_cycles(self) -> None:
        # DFS cycle detection
        visiting: set[int] = set()
        visited: set[int] = set()

        def dfs(node: int) -> None:
            if node in visited:
                return
            if node in visiting:
                raise ValueError(f"Cycle detected in semantic parents involving {node}")
            visiting.add(node)
            rec = self._concepts[node]
            for p in rec.parents:
                if p in self._concepts:
                    dfs(p)
            visiting.remove(node)
            visited.add(node)

        for cid in self._concepts:
            dfs(cid)

    def to_linkml_instances(
        self,
        *,
        doc_id: str | None = None,
        name: str | None = None,
        description: str | None = None,
        include_groups: bool = True,
        concept_class_uri: str = "OmopConcept",
        group_class_uri: str = "ConceptGroup",
    ) -> dict[str, Any]:
        """
        Emit a dict suitable for YAML dumping as a LinkML instances file.

        This is your "round-trip" mechanism (load -> registry -> emit).
        """
        out: dict[str, Any] = {}
        if doc_id:
            out["id"] = doc_id
        if name:
            out["name"] = name
        if description:
            out["description"] = description

        # concepts
        for c in sorted(self._concepts.values(), key=lambda x: x.concept_id):
            out[c.label.replace(" ", "_")] = {
                "class_uri": concept_class_uri,
                "concept_id": c.concept_id,
                "label": c.label,
                "role": c.role,
                **({"parent_concepts": list(c.parents)} if c.parents else {}),
                **({"notes": c.notes} if c.notes else {}),
            }

        if include_groups:
            for g in sorted(self._groups.values(), key=lambda x: x.name.lower()):
                out[g.name.replace(" ", "_")] = {
                    "class_uri": group_class_uri,
                    "name": g.name,
                    "role": g.role,
                    "members": list(g.members),
                    **({"notes": g.notes} if g.notes else {}),
                }

        return out


    def with_concepts(self, concepts: Iterable[ConceptRecord]) -> "ConceptRegistry":
        return ConceptRegistry(concepts=concepts, groups=self._groups.values(), schema=self._schema)

    def with_groups(self, groups: Iterable[ConceptGroupRecord]) -> "ConceptRegistry":
        return ConceptRegistry(concepts=self._concepts.values(), groups=groups, schema=self._schema)

    def with_schema(self, schema: SchemaInfo | None) -> "ConceptRegistry":
        return ConceptRegistry(concepts=self._concepts.values(), groups=self._groups.values(), schema=schema)

    def with_added_concept(self, concept: ConceptRecord) -> "ConceptRegistry":
        concepts = list(self._concepts.values())
        concepts.append(concept)
        return ConceptRegistry(concepts=concepts, groups=self._groups.values(), schema=self._schema)

    def with_updated_concept(self, concept_id: int, **changes: Any) -> "ConceptRegistry":
        base = self.get(concept_id)
        updated = replace(base, **changes)
        concepts = [updated if c.concept_id == concept_id else c for c in self._concepts.values()]
        return ConceptRegistry(concepts=concepts, groups=self._groups.values(), schema=self._schema)


    def diff(self, other: "ConceptRegistry") -> "RegistryDiff":
        return RegistryDiff.from_registries(self, other)

    def merge(self, other: "ConceptRegistry", *, strategy: str = "prefer_self") -> "ConceptRegistry":
        """
        strategy:
          - prefer_self: keep self on conflicts
          - prefer_other: keep other on conflicts
          - error: raise on conflicts
        """
        concepts: dict[int, ConceptRecord] = dict(self._concepts)
        groups: dict[str, ConceptGroupRecord] = dict(self._groups)

        # concepts
        for cid, c2 in other._concepts.items():
            if cid not in concepts:
                concepts[cid] = c2
                continue
            c1 = concepts[cid]
            if c1 != c2:
                if strategy == "prefer_other":
                    concepts[cid] = c2
                elif strategy == "error":
                    raise ValueError(f"Conflict concept_id={cid}: {c1} vs {c2}")

        # groups (by lower name key)
        for gk, g2 in other._groups.items():
            if gk not in groups:
                groups[gk] = g2
                continue
            g1 = groups[gk]
            if g1 != g2:
                if strategy == "prefer_other":
                    groups[gk] = g2
                elif strategy == "error":
                    raise ValueError(f"Conflict group={gk}: {g1} vs {g2}")

        # schema: keep self schema unless missing
        schema = self._schema if self._schema is not None else other._schema
        return ConceptRegistry(concepts=concepts.values(), groups=groups.values(), schema=schema)


    def summary(self) -> dict[str, int]:
        return {
            "concepts": len(self._concepts),
            "groups": len(self._groups),
            "roles": len(self._by_role),
        }

    def __repr__(self) -> str:
        role_counts = {role: len(cids) for role, cids in self._by_role.items()}
        top = sorted(role_counts.items(), key=lambda x: (-x[1], x[0]))[:6]
        # major = ", ".join(f"{r}:{n}" for r, n in top)
        # more = "" if len(role_counts) <= 6 else f", …(+{len(role_counts)-6})"
        schema_flag = "schema" if self._schema else "no-schema"
        return (
            "<ConceptRegistry "
            f"{schema_flag} "
            f"concepts={len(self._concepts)} "
            f"groups={len(self._groups)} "
            f"roles={len(self._by_role)}>"
        )

    def __str__(self) -> str:
        lines = [
            "ConceptRegistry:",
            f"  Concepts: {len(self._concepts)}",
            f"  Groups:   {len(self._groups)}",
            f"  Schema:   {'yes' if self._schema else 'no'}",
            "  Roles:",
        ]
        for role, cids in sorted(self._by_role.items()):
            desc = self.describe_role(role)
            suffix = f" — {desc}" if desc else ""
            lines.append(f"    - {role}: {len(cids)}{suffix}")
        return "\n".join(lines)

    def _repr_html_(self) -> str:
        # lightweight: no external deps, works in notebooks
        rows = []
        for role in sorted(self._by_role.keys()):
            rows.append(
                f"<tr><td><code>{role}</code></td>"
                f"<td style='text-align:right'>{len(self._by_role[role])}</td>"
                f"<td>{(self.describe_role(role) or '')}</td></tr>"
            )
        return f"""
        <div style="font-family: system-ui, sans-serif">
          <div style="margin-bottom:6px;">
            <b>ConceptRegistry</b>
            <span style="color:#666">({len(self._concepts)} concepts, {len(self._groups)} groups)</span>
          </div>
          <table style="border-collapse:collapse; width:100%; max-width:720px">
            <thead>
              <tr>
                <th style="text-align:left; border-bottom:1px solid #ddd; padding:4px;">Role</th>
                <th style="text-align:right; border-bottom:1px solid #ddd; padding:4px;">Count</th>
                <th style="text-align:left; border-bottom:1px solid #ddd; padding:4px;">Description</th>
              </tr>
            </thead>
            <tbody>{''.join(rows)}</tbody>
          </table>
        </div>
        """
    

@dataclass(frozen=True)
class RegistryDiff:
    added_concepts: tuple[int, ...]
    removed_concepts: tuple[int, ...]
    changed_concepts: tuple[int, ...]
    added_groups: tuple[str, ...]
    removed_groups: tuple[str, ...]
    changed_groups: tuple[str, ...]

    @classmethod
    def from_registries(cls, a: ConceptRegistry, b: ConceptRegistry) -> "RegistryDiff":
        a_ids = set(a._concepts.keys())
        b_ids = set(b._concepts.keys())

        added = tuple(sorted(b_ids - a_ids))
        removed = tuple(sorted(a_ids - b_ids))
        changed = tuple(sorted(cid for cid in (a_ids & b_ids) if a._concepts[cid] != b._concepts[cid]))

        a_g = set(a._groups.keys())
        b_g = set(b._groups.keys())

        g_added = tuple(sorted(b_g - a_g))
        g_removed = tuple(sorted(a_g - b_g))
        g_changed = tuple(sorted(g for g in (a_g & b_g) if a._groups[g] != b._groups[g]))

        return cls(
            added_concepts=added,
            removed_concepts=removed,
            changed_concepts=changed,
            added_groups=g_added,
            removed_groups=g_removed,
            changed_groups=g_changed,
        )

    def __repr__(self) -> str:
        return (
            "<RegistryDiff "
            f"+c={len(self.added_concepts)} "
            f"-c={len(self.removed_concepts)} "
            f"~c={len(self.changed_concepts)} "
            f"+g={len(self.added_groups)} "
            f"-g={len(self.removed_groups)} "
            f"~g={len(self.changed_groups)}>"
        )