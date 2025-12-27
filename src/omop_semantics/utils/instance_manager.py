from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Mapping
from ruamel.yaml import YAML

from ..schema.registry import ConceptRecord, ConceptGroupRecord

_yaml = YAML(typ="safe")


def _as_mapping(x: Any) -> Mapping[str, Any] | None:
    return x if isinstance(x, dict) else None


def validate_symbol_refs(
    *,
    data: dict[str, dict],
    symbol_to_concept_id: dict[str, int],
    slots: dict[str, str],  # slot_name → human label
) -> None:
    """
    Validate that symbolic references in specified slots resolve.
    """
    for name, obj in data.items():
        if not isinstance(obj, dict):
            continue
        for slot, label in slots.items():
            for ref in obj.get(slot, []):
                if isinstance(ref, str) and ref not in symbol_to_concept_id:
                    raise ValueError(
                        f"Unresolved {label} reference '{ref}' "
                        f"in {name}.{slot}"
                    )

def resolve_refs(
    refs: Iterable[int | str],
    symbol_to_concept_id: dict[str, int],
) -> tuple[int, ...]:
    return tuple(
        symbol_to_concept_id[r] if isinstance(r, str) else r
        for r in refs
    )

def load_instances_any(*instance_paths: Path) -> tuple[list[ConceptRecord], list[ConceptGroupRecord]]:
    """
    Load LinkML instance YAML files without requiring generated LinkML Python classes.

    Accepts dict-like instance documents, where top-level keys may include
    header fields (id/name/description) and instance blocks.
    """
    concepts: list[ConceptRecord] = []
    groups: list[ConceptGroupRecord] = []
    symbol_to_concept_id: dict[str, int] = {}

    for path in instance_paths:
        data = _yaml.load(path.read_text())
        if not isinstance(data, dict):
            raise ValueError(f"Instance file {path} did not parse as a mapping/dict")

        for name, obj in data.items():
            if "concept_id" in obj:
                symbol_to_concept_id[name] = obj["concept_id"]

        validate_symbol_refs(
            data=data,
            symbol_to_concept_id=symbol_to_concept_id,
            slots={"parent_concepts": "parent concept", "members": "group member"},
        )

        for key, obj in data.items():
            # skip document headers
            if key in {"id", "name", "title", "description", "imports", "prefixes"}:
                continue

            m = _as_mapping(obj)
            if not m:
                # allow stray scalars
                continue

            if "concept_id" in m:
                concept_id = int(m["concept_id"])
                label = str(m.get("label") or key)
                role = str(m.get("role") or "metadata")

                parents_ids=resolve_refs(
                            obj.get("parent_concepts", []),
                            symbol_to_concept_id,
                        )

                concepts.append(
                    ConceptRecord(
                        concept_id=concept_id,
                        label=label,
                        role=role,
                        parents=tuple(parents_ids),
                        notes=(str(m["notes"]) if m.get("notes") is not None else None),
                    )
                )
                continue

            if "members" in m:
                name = str(m.get("name") or key)
                role = str(m.get("role") or "metadata")
                member_ids = resolve_refs(
                            obj["members"],
                            symbol_to_concept_id,
                        )
                groups.append(
                    ConceptGroupRecord(
                        name=name,
                        role=role,
                        members=tuple(member_ids),
                        notes=(str(m["notes"]) if m.get("notes") is not None else None),
                    )
                )
                continue

    return concepts, groups
