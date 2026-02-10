from dataclasses import dataclass
from ruamel.yaml import YAML
from pathlib import Path
from typing import Sequence, Optional, Tuple
from typing import Union
from html import escape
from .pretty import preview
import logging
logger = logging.getLogger(__name__)


_yaml = YAML(typ="safe")

@dataclass(frozen=True)
class LookupSpec:
    """
    Specification for looking up concepts in the registry based on schema-defined constraints.

    We want to be able to express rules like 
    "“Units must be standard Measurement units from WeightUnits group; unknown allowed.”"

    The LookupSpec captures both semantic constraints (e.g. role/group/parent constraints) 
    and OMOP-level constraints (e.g. domain/class/vocabulary/standardness), as well as unknown 
    handling behavior.
    """

    name: str

    # Semantic constraints (registry-level)
    role: str | None = None                      # concept must have this semantic role
    allowed_groups: Sequence[str] | None = None  # e.g. WeightUnits
    allowed_roles: Sequence[str] | None = None   # alternative to role
    parent_role: str | None = None               # semantic parent constraint

    # OMOP-level constraints (interpreted by omop_alchemy)
    domain_id: str | None = None
    concept_class_id: Sequence[str] | None = None
    vocabulary_id: Sequence[str] | None = None
    standard_only: bool = True

    # Unknown handling
    allow_unknown: bool = False
    unknown_role: str = "unknown"

@dataclass(frozen=True)
class ConceptRecord:
    concept_id: int
    label: str
    role: str
    parents: Tuple[int, ...] = ()
    notes: Optional[str] = None

    value_type: str | None = None   # "numeric", "ordinal", "boolean", "categorical"


    def __repr__(self) -> str:
        return (
            "<ConceptRecord "
            f"id={self.concept_id} "
            f"label={self.label!r} "
            f"role={self.role}"
            f"{' parents=' + str(len(self.parents)) if self.parents else ''}"
            f"{' value_type=' + self.value_type if self.value_type else ''}"
            ">"
        )
    

    def __str__(self) -> str:
        lines = [
            f"ConceptRecord {self.concept_id}",
            f"  Label: {self.label}",
            f"  Role:  {self.role}",
        ]
        if self.parents:
            lines.append(f"  Parents: {', '.join(map(str, self.parents))}")
        if self.value_type:
            lines.append(f"  Value type: {self.value_type}")
        if self.notes:
            lines.append(f"  Notes: {self.notes}")
        return "\n".join(lines)

    def _repr_html_(self) -> str:
        rows = [
            f"<tr><th>ID</th><td>{self.concept_id}</td></tr>",
            f"<tr><th>Label</th><td>{escape(self.label)}</td></tr>",
            f"<tr><th>Role</th><td><code>{escape(self.role)}</code></td></tr>",
        ]
        if self.value_type:
            rows.append(f"<tr><th>Value type</th><td>{escape(self.value_type)}</td></tr>")
        if self.parents:
            rows.append(f"<tr><th>Parents</th><td>{', '.join(map(str, self.parents))}</td></tr>")
        if self.notes:
            rows.append(f"<tr><th>Notes</th><td>{escape(self.notes)}</td></tr>")

        return f"""
        <div style="font-family: system-ui, sans-serif; max-width: 520px">
          <b>ConceptRecord</b>
          <table style="border-collapse: collapse; margin-top: 6px">
            {''.join(rows)}
          </table>
        </div>
        """

@dataclass(frozen=True)
class ConceptGroupRecord:
    name: str
    role: str
    members: tuple[int, ...]
    notes: Optional[str] = None
    kind: str | None = None       # e.g. "unit_set", "value_set", "axis", "modifier_set"
    exclusive: bool = False       # if true, values should be mutually exclusive


    def __repr__(self) -> str:
        return (
            "<ConceptGroupRecord "
            f"name={self.name!r} "
            f"role={self.role} "
            f"members={len(self.members)}"
            f"{' kind=' + self.kind if self.kind else ''}"
            f"{' exclusive' if self.exclusive else ''}"
            ">"
        )

    def __str__(self) -> str:
        lines = [
            f"ConceptGroup {self.name}",
            f"  Role: {self.role}",
            f"  Members: {len(self.members)}",
        ]
        if self.kind:
            lines.append(f"  Kind: {self.kind}")
        if self.exclusive:
            lines.append("  Exclusive: true")
        if self.notes:
            lines.append(f"  Notes: {self.notes}")
        return "\n".join(lines)

    def _repr_html_(self) -> str:
        member_preview = preview([str(m) for m in self.members])

        rows = [
            f"<tr><th>Name</th><td>{escape(self.name)}</td></tr>",
            f"<tr><th>Role</th><td><code>{escape(self.role)}</code></td></tr>",
            f"<tr><th>Members</th><td>{len(self.members)} ({escape(member_preview)})</td></tr>",
        ]
        if self.kind:
            rows.append(f"<tr><th>Kind</th><td>{escape(self.kind)}</td></tr>")
        if self.exclusive:
            rows.append("<tr><th>Exclusive</th><td>true</td></tr>")
        if self.notes:
            rows.append(f"<tr><th>Notes</th><td>{escape(self.notes)}</td></tr>")

        return f"""
        <div style="font-family: system-ui, sans-serif; max-width: 560px">
          <b>ConceptGroup</b>
          <table style="border-collapse: collapse; margin-top: 6px">
            {''.join(rows)}
          </table>
        </div>
        """

@dataclass(frozen=True)
class RoleDefinition:
    name: str
    description: str | None = None
    category: str | None = None   # e.g. "clinical", "structural", "metadata"

@dataclass(frozen=True)
class SchemaInfo:
    roles: dict[str, RoleDefinition]
    classes: set[str]

    @classmethod
    def from_linkml(cls, *schema_paths: Path | dict) -> "SchemaInfo":
        return load_schema_info(*schema_paths)

    def __repr__(self) -> str:
        roles = sorted(self.roles)
        role_preview = ", ".join(roles[:4])
        if len(roles) > 4:
            role_preview += f", … (+{len(roles) - 4})"

        return (
            "<SchemaInfo "
            f"roles={len(self.roles)} "
            f"classes={len(self.classes)} "
            f"[{role_preview}]>"
        )

    def __str__(self) -> str:
        lines = [
            "SchemaInfo:",
            f"  Roles:   {len(self.roles)}",
            f"  Classes: {len(self.classes)}",
            "  Role definitions:",
        ]
        for r, rd in sorted(self.roles.items()):
            if rd.description:
                lines.append(f"    - {r}: {rd.description}")
            else:
                lines.append(f"    - {r}")
        return "\n".join(lines)


    def _repr_html_(self) -> str:
        role_rows = []
        for name, rd in sorted(self.roles.items()):
            desc = rd.description or ""
            cat = rd.category or ""
            role_rows.append(
                f"<tr>"
                f"<td><code>{escape(name)}</code></td>"
                f"<td>{escape(desc)}</td>"
                f"<td>{escape(cat)}</td>"
                f"</tr>"
            )

        class_preview = preview(sorted(self.classes))

        return f"""
        <div style="font-family: system-ui, sans-serif; max-width: 720px">
          <div style="margin-bottom: 6px">
            <b>SchemaInfo</b>
            <span style="color:#666">({len(self.roles)} roles, {len(self.classes)} classes)</span>
          </div>

          <div style="margin-bottom: 6px">
            <b>Classes:</b> {escape(class_preview)}
          </div>

          <table style="border-collapse: collapse; width: 100%">
            <thead>
              <tr>
                <th style="text-align:left; border-bottom:1px solid #ddd; padding:4px;">Role</th>
                <th style="text-align:left; border-bottom:1px solid #ddd; padding:4px;">Description</th>
                <th style="text-align:left; border-bottom:1px solid #ddd; padding:4px;">Category</th>
              </tr>
            </thead>
            <tbody>
              {''.join(role_rows)}
            </tbody>
          </table>
        </div>
        """    


def load_schema_info(*schema_paths: Path | dict) -> SchemaInfo:
    roles: dict[str, RoleDefinition] = {}
    classes: set[str] = set()
    
    for src in schema_paths:
        if isinstance(src, Path):
            try:
                text = src.read_text()
                data = _yaml.load(text)
            except Exception as e:
                logger.exception(f"Failed to load schema YAML from {src}")
                raise
            src_label = str(src)        
        elif isinstance(src, dict):
            data = src
            src_label = "<dict>"
        else:
            raise TypeError(f"Unsupported schema path type: {type(src)}")

        if not isinstance(data, dict):
            logger.warning(f"Schema file {src_label} parsed to None (empty or comments-only). Skipping.")
            continue

        # enums to roles
        enums = data.get("enums") or {}
        for enum_name, enum_def in enums.items():

            if enum_name != "ConceptRole":
                continue
            pv = enum_def.get("permissible_values") if isinstance(enum_def, dict) else None
            if not isinstance(pv, dict):
                logger.warning(f"Schema file {src_label} enum ConceptRole has no permissible_values mapping. Skipping roles.")
                continue

            for role, role_def in pv.items():
                desc = role_def.get("description") if isinstance(role_def, dict) else None
                roles[role] = RoleDefinition(name=role, description=desc)

        # classes
        classes_block = data.get("classes") or {}
        for cls in classes_block.keys():
            classes.add(cls)
        
        if "classes" in data:
            logger.info(f"Loaded {len(classes_block)} classes from {src_label}")


    return SchemaInfo(roles=roles, classes=classes)

