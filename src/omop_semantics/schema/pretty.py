from html import escape
from typing import Iterable, Sequence

def preview(items: Iterable[str], *, limit: int = 4) -> str:
    items = list(items)
    head = ", ".join(items[:limit])
    if len(items) > limit:
        return f"{head}, … (+{len(items) - limit})"
    return head

def html_kv(label: str, value: str) -> str:
    return f"<tr><th style='text-align:left; padding:4px; color:#555'>{escape(label)}</th><td style='padding:4px'>{escape(value)}</td></tr>"

def html_list(items: Iterable[str]) -> str:
    return "<ul>" + "".join(f"<li>{escape(i)}</li>" for i in items) + "</ul>"

def html_table(headers: Sequence[str], rows: Sequence[Sequence[str]]) -> str:
    head_html = "".join(
        f"<th style='text-align:left; border-bottom:1px solid #ddd; padding:4px;'>{escape(h)}</th>"
        for h in headers
    )
    body_html = "".join(
        "<tr>" + "".join(f"<td style='padding:4px; vertical-align:top'>{cell}</td>" for cell in row) + "</tr>"
        for row in rows
    )
    return f"""
    <table style="border-collapse:collapse; width:100%">
      <thead><tr>{head_html}</tr></thead>
      <tbody>{body_html}</tbody>
    </table>
    """