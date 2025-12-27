from dataclasses import dataclass
from ruamel.yaml import YAML
from pathlib import Path

_yaml = YAML(typ="safe")

@dataclass(frozen=True)
class RoleDefinition:
    name: str
    description: str | None = None

@dataclass(frozen=True)
class SchemaInfo:
    roles: dict[str, RoleDefinition]
    classes: set[str]

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
    
def load_schema_info(*schema_paths: Path) -> SchemaInfo:
    roles: dict[str, RoleDefinition] = {}
    classes: set[str] = set()
    
    for path in schema_paths:
        data = _yaml.load(path.read_text())

        # enums to roles
        for enum_name, enum_def in data.get("enums", {}).items():
            if enum_name == "ConceptRole":
                for role, role_def in enum_def.get("permissible_values", {}).items():
                    roles[role] = RoleDefinition(
                        name=role,
                        description=(
                            role_def.get("description")
                            if isinstance(role_def, dict)
                            else None
                        ),
                    )

        # classes
        for cls in data.get("classes", {}).keys():
            classes.add(cls)

    return SchemaInfo(roles=roles, classes=classes)
