from __future__ import annotations
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, runtime_checkable, Protocol, Any, cast
from linkml_runtime.loaders.yaml_loader import YAMLLoader
from linkml_runtime.utils.schemaview import SchemaView, SchemaDefinition
from html import escape

logger = logging.getLogger(__name__)

def as_list(x) -> list:
    if x is None:
        return []
    if isinstance(x, list):
        return x
    return [x]

def h(x: object) -> str:
    if x is None:
        return ""
    if isinstance(x, Html):
        return x.raw
    return escape(str(x))

def td(val: object, *, header: bool = False, align: str | None = None) -> str:
    tag = "th" if header else "td"
    style = []
    if align:
        style.append(f"text-align:{align}")
    style_attr = f" style=\"{'; '.join(style)}\"" if style else ""
    return f"<{tag}{style_attr}>{h(val)}</{tag}>"


def tr(cells: Iterable[object], *, header: bool = False, align: list[str] | None = None) -> str:
    """
    Render a <tr> where each cell is <td> or <th> depending on `header`.

    Example:
        tr(["Name", "Role", "Count"], header=True)
        tr(["Demography", "demographic", 3])
    """
    align = align or []
    tds = []
    for i, cell in enumerate(cells):
        a = align[i] if i < len(align) else None
        tds.append(td(cell, header=header, align=a))
    return f"<tr>{''.join(tds)}</tr>"

def table(rows: list[str], *, header: list[str] | None = None) -> str:
    thead = ""
    if header:
        thead = f"<thead>{tr(header, header=True)}</thead>"

    tbody = f"<tbody>{''.join(rows)}</tbody>"
    return f"""
    <table style="border-collapse: collapse; width: 100%;">
      {thead}
      {tbody}
    </table>
    """

@dataclass(frozen=True)
class Html:
    raw: str

    def __html__(self) -> str:
        return self.raw
    
@runtime_checkable
class RegistryLike(Protocol):
    name: str
    description: Optional[str]
    groups: list[Any]

@dataclass
class RegistryObject:
    symbol: str
    instance: object          # LinkML runtime object (Pydantic / dataclass)
    schema_view: SchemaView   # for reflection

    @property
    def class_uri(self) -> str:
        return type(self.instance).__name__
    
    @property
    def schema(self) -> SchemaDefinition:
        _schema = self.schema_view.schema
        if _schema is None:
            raise ValueError("SchemaView does not have a loaded schema")
        return _schema
    
    @property
    def label(self) -> str:
        try:
            return self.schema.name
        except ValueError:
            return "[unknown schema name]"

    def get(self, slot: str, default=None):
        return getattr(self.instance, slot, default)

    def slots(self) -> dict:
        cls = self.class_uri
        return {
            s: getattr(self.instance, s)
            for s in self.schema_view.class_slots(cls)
            if hasattr(self.instance, s)
        }
    

    def summarise_value(self, v: object) -> Html | str:
        """
        Turn any slot value into a compact HTML-safe summary.
        """
        if v is None:
            return Html("<span style='color:#999'>(none)</span>")

        # RegistryObject reference
        if isinstance(v, RegistryObject):
            return Html(f"<code>{h(v.symbol)}</code> <span style='color:#666'>({h(v.class_uri)})</span>")

        # LinkML object reference
        if hasattr(v, "__dict__"):
            name = getattr(v, "name", None)
            cls = type(v).__name__
            if name:
                return Html(f"<code>{h(name)}</code> <span style='color:#666'>({h(cls)})</span>")
            return Html(f"<span style='color:#666'>({h(cls)})</span>")

        # List of things
        if isinstance(v, list):
            if not v:
                return Html("<span style='color:#999'>(none)</span>")
            parts = [self.summarise_value(x) for x in v[:3]]
            more = f" …(+{len(v) - 3})" if len(v) > 3 else ""
            joined = ", ".join(h(p) for p in parts)
            return Html(f"{joined}{more}")

        # Scalar
        return h(v)
    

    def to_row(
        self,
        *,
        columns: list[str] | None = None,
        include_class: bool = False,
    ) -> list[Html | str]:
        """
        Generate a flexible row for tabular rendering.

        Parameters
        ----------
        columns:
            Slot names to include (in order). If None, use all slots for class.
        include_class:
            Whether to include class_uri as the first column.
        """
        row: list[Html | str] = []

        if include_class:
            row.append(Html(f"<code>{h(self.class_uri)}</code>"))

        slots = self.slots()

        if columns is None:
            for k, v in slots.items():
                row.append(self.summarise_value(v))
        else:
            for col in columns:
                row.append(self.summarise_value(slots.get(col)))

        return row

@dataclass
class RegistryGroupRuntime:
    name: str
    role: Optional[str]
    members: list[RegistryObject]
    notes: Optional[str] = None


    def _repr_html_(self) -> str:
        # Choose sensible default columns for mixed content
        # (works for OmopTemplate, OmopConcept, OmopGroup, OmopEnum)
        header = ["Name", "Class", "Role", "CDM table", "Concept slot", "Value slot"]

        rows: list[str] = []

        for obj in self.members:
            slots = obj.slots()

            name = slots.get("name") or obj.symbol
            role = slots.get("role")
            cdm_table = slots.get("cdm_table")
            concept_slot = slots.get("concept_slot")
            value_slot = slots.get("value_slot")

            rows.append(
                tr(
                    [
                        obj.summarise_value(name),
                        Html(f"<code>{h(obj.class_uri)}</code>"),
                        obj.summarise_value(role),
                        obj.summarise_value(cdm_table),
                        obj.summarise_value(concept_slot),
                        obj.summarise_value(value_slot),
                    ]
                )
            )

        tbl = table(
            rows,
            header=header,
        )

        return f"""
        <div style="margin: 12px 0; padding: 10px; border: 1px solid #eee; border-radius: 8px;">
          <div style="font-weight: 600; font-size: 16px;">{h(self.name)}</div>
          <div style="color:#666; font-size: 13px; margin-bottom:4px;">
            role: <code>{h(self.role)}</code>
          </div>
          {f"<div style='color:#444; margin-bottom:8px;'>{h(self.notes)}</div>" if self.notes else ""}
          {tbl}
        </div>
        """

@dataclass
class RegistryRuntime:
    name: str
    description: Optional[str]
    groups: List[RegistryGroupRuntime]

    def _repr_html_(self) -> str:
        parts: list[str] = []

        parts.append(f"""
        <div style="font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif; max-width: 1100px;">
          <div style="margin-bottom: 12px;">
            <div style="font-size: 18px; font-weight: 700;">{h(self.name)}</div>
            <div style="color:#666; font-size: 13px;">
              {h(self.description) if self.description else ""}
            </div>
          </div>
        """)

        for g in self.groups:
            parts.append(g._repr_html_())

        parts.append("</div>")
        return "".join(parts)
    

from .utils import load_pydantic_class

class RegistryManager:
    def __init__(self, schema_path: Path, registry_instance_path: Path):
        self.schema_path = schema_path
        self.schema_view = SchemaView(str(schema_path))

        schema = self.schema_view.schema
        if schema is None:
            raise ValueError(f"Failed to load schema from {schema_path}")
        
        classes = schema.classes
        if classes is None or "Registry" not in classes:
            raise ValueError(f"Schema {schema_path} does not define a 'Registry' class")
        
        registry_class = classes.get("Registry") # type: ignore
        if registry_class is None:
            raise ValueError(f"Failed to resolve 'Registry' class in schema {schema_path}")

        self.registry_root = load_pydantic_class("Registry", schema_path)
        self.objects: Dict[str, RegistryObject] = {}
        self._index_instances(self.registry_root)
        self.registry = self._build_registry_runtime()

    def _index_instances(self, root_obj):
        """
        Walk the loaded LinkML object graph and wrap all named objects.
        """
        for slot in self.schema_view.class_slots('Registry'):
            val = getattr(root_obj, slot, None)

            if isinstance(val, list):
                for v in val:
                    self._register_object(v)
            elif val is not None:
                self._register_object(val)

    def _register_object(self, obj):
        if obj is None:
            return

        name = getattr(obj, "name", None)
        if name:
            if name not in self.objects:
                self.objects[name] = RegistryObject(
                    symbol=name,
                    instance=obj,
                    schema_view=self.schema_view,
                )

        cls_name = obj.__class__.__name__
        for slot in self.schema_view.class_slots(cls_name):
            val = getattr(obj, slot, None)
            if isinstance(val, list):
                for v in val:
                    if hasattr(v, "__dict__"):
                        self._register_object(v)
            elif hasattr(val, "__dict__"):
                self._register_object(val)


    def _build_registry_runtime(self) -> RegistryRuntime:
        groups: List[RegistryGroupRuntime] = []

        for g in getattr(self.registry_root, "groups", []) or []:
            members = []
            for sym in getattr(g, "members", []) or []:
                if isinstance(sym, str):
                    obj = self.objects.get(sym)
                else:
                    name = getattr(sym, "name", None)
                    obj = self.objects.get(name) if isinstance(name, str) else None
                if obj:
                    members.append(obj)

            groups.append(
                RegistryGroupRuntime(
                    name=g.name,
                    role=getattr(g, "role", None),
                    members=members,
                    notes=getattr(g, "notes", None),
                )
            )
        root = cast(RegistryLike, self.registry_root)
        name = getattr(root, "name", "Registry")
        return RegistryRuntime(
            name=name,
            description=getattr(root, "description", None),
            groups=groups,
        )
    
    def get(self, symbol: str) -> RegistryObject:
        return self.objects[symbol]

    def all_objects(self) -> list[RegistryObject]:
        return list(self.objects.values())

    def groups(self) -> list[RegistryGroupRuntime]:
        return self.registry.groups