from typing import Iterable, TYPE_CHECKING
from html import escape
from dataclasses import dataclass
from omop_semantics.schema.generated_models.omop_semantic_registry import (
    OmopConcept, 
    OmopGroup, 
    OmopEnum, 
    RegistryFragment, 
    OmopSemanticObject, 
    OmopTemplate,
    RegistryGroup
)
if TYPE_CHECKING:
    from .resolver import SemanticProfileRuntime


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

    def _repr_html_(self) -> str:
        return self.raw
    

def render_semantic_object(obj: OmopSemanticObject | None) -> Html:
    if obj is None:
        return Html("<em>None</em>")

    if isinstance(obj, OmopConcept):
        return Html(
            f"<b>Concept</b>: {h(obj.name)} "
            f"(concept_id={h(obj.concept_id)}, label={h(obj.label)})"
        )

    if isinstance(obj, OmopGroup):
        parents = ", ".join(
            f"{h(p.concept_id)} ({h(p.label)})"
            for p in as_list(obj.parent_concepts)
            if p.concept_id is not None
        )
        return Html(
            f"<b>Group</b>: {h(obj.name)}<br/>"
            f"<small>Anchors: {parents or '—'}</small>"
        )

    if isinstance(obj, OmopEnum):
        members = ", ".join(
            f"{h(c.concept_id)} ({h(c.label)})"
            for c in as_list(obj.enum_members)
            if c.concept_id is not None
        )
        return Html(
            f"<b>Enum</b>: {h(obj.name)}<br/>"
            f"<small>Members: {members or '—'}</small>"
        )

    return Html(f"<code>{h(type(obj).__name__)}</code>")

def render_profile_object(obj: dict) -> Html:
    class_uri = obj.get("class_uri")

    if class_uri == "OmopConcept":
        return Html(
            f"<b>Concept</b>: {h(obj.get('name'))} "
            f"(concept_id={h(obj.get('concept_id'))}, "
            f"label={h(obj.get('label'))})"
        )

    if class_uri == "OmopGroup":
        anchors = as_list(obj.get("parent_concepts"))
        anchors_str = ", ".join(
            f"{a.get('concept_id')} ({a.get('label')})"
            for a in anchors
            if isinstance(a, dict)
        )
        return Html(
            f"<b>Group</b>: {h(obj.get('name'))}"
            + (f"<br/><small>Anchors: {h(anchors_str)}</small>" if anchors_str else "")
        )

    if class_uri == "OmopEnum":
        members = as_list(obj.get("enum_members"))
        members_str = ", ".join(
            f"{m.get('concept_id')} ({m.get('label')})"
            for m in members
            if isinstance(m, dict)
        )
        return Html(
            f"<b>Enum</b>: {h(obj.get('name'))}"
            + (f"<br/><small>Members: {h(members_str)}</small>" if members_str else "")
        )

    if class_uri == "RegistryGroup":
        members = ", ".join(as_list(obj.get("members")))
        return Html(f"<b>RegistryGroup</b>: {h(obj.get('name'))}<br/><small>Members: {h(members)}</small>")

    if class_uri == "OmopTemplate":
        return Html(f"<b>Template</b>: {h(obj.get('name'))}")
    
    if class_uri == "OmopValueSet":
        return Html(f"<b>ValueSet</b>: {h(obj.get('name'))}")
    
    return Html(f"<em>Unknown:</em> {h(class_uri)}")

def render_template_row(tpl: OmopTemplate) -> str:
    return tr([
        tpl.name,
        tpl.role,
        tpl.cdm_table,
        tpl.concept_slot,
        tpl.value_slot or "",
        render_semantic_object(tpl.entity_concept),
        render_semantic_object(tpl.value_concept),
    ])

def render_registry_group(group: RegistryGroup) -> Html:
    rows = [
        render_template_row(tpl)
        for tpl in as_list(group.registry_members)
    ]

    html = table(
        rows,
        header=[
            "Template",
            "Role",
            "CDM Table",
            "Concept Slot",
            "Value Slot",
            "Entity Concept",
            "Value Concept",
        ],
    )

    return Html(
        f"<h3>{h(group.name)} ({h(group.role)})</h3>"
        f"{html}"
        f"<p><em>{h(group.notes)}</em></p>" if group.notes else
        f"<h3>{h(group.name)} ({h(group.role)})</h3>{html}"
    )

def render_registry_fragment(fragment: RegistryFragment) -> Html:
    blocks = []
    for group in as_list(fragment.groups):
        blocks.append(render_registry_group(group).raw)

    return Html("".join(blocks))

def render_compiled_templates(compiled: list[dict]) -> Html:
    rows = []
    for c in compiled:
        rows.append(tr([
            c["name"],
            c["role"],
            c["cdm_table"],
            c["concept_slot"],
            c["value_slot"] or "",
            ", ".join(map(str, sorted(c["entity_concept_ids"]))),
            ", ".join(map(str, sorted(c["value_concept_ids"] or []))),
        ]))

    return Html(table(
        rows,
        header=[
            "Template",
            "Role",
            "CDM Table",
            "Concept Slot",
            "Value Slot",
            "Entity Concept IDs",
            "Value Concept IDs",
        ],
    ))

def render_profile_groups(profile: "SemanticProfileRuntime") -> Html:
    rows = []
    for name, obj in profile.list_groups().items():
        rows.append(tr([
            name,
            obj.get("role"),
            obj.get("notes", ""),
            ", ".join(as_list(obj.get("members", []))),
        ]))

    return Html(table(
        rows,
        header=["Name", "Role", "Notes", "Members"],
    ))