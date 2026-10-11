"""Mermaid flowchart text. Labels are quoted and escaped so a label can never break the syntax."""

from __future__ import annotations

from typing import Literal

from ..ir import GraphDocument
from ..security import sanitize_label
from .svg import edge_rows

SHAPES = {
    "SystemNode": ('(["', '"])'), "TaskNode": ('["', '"]'), "ContextNode": ('("', '")'),
    "ConstraintNode": ('{{"', '"}}'), "ToolNode": ('[["', '"]]'), "ExampleNode": ('>"', '"]'),
}  # fmt: skip
CLASSES = {
    "SystemNode": "fill:#ece6ff,stroke:#8b6cf0", "TaskNode": "fill:#e1eefc,stroke:#2f7fe0",
    "ContextNode": "fill:#dff6ee,stroke:#14a578", "ConstraintNode": "fill:#fdf1d3,stroke:#c78a00",
    "ToolNode": "fill:#dcf3f7,stroke:#0f9fb5", "ExampleNode": "fill:#fbe3f0,stroke:#d6459a",
}  # fmt: skip


def _q(text: str) -> str:
    """Escape for a double-quoted Mermaid label."""
    t = sanitize_label(text)[:70]
    for a, b in (
        ("&", "#amp;"),
        ('"', "#quot;"),
        ("<", "#lt;"),
        (">", "#gt;"),
        ("[", "#91;"),
        ("]", "#93;"),
        ("{", "#123;"),
        ("}", "#125;"),
        ("|", "#124;"),
        ("`", "#96;"),
    ):
        t = t.replace(a, b)
    return t


def to_mermaid(doc: GraphDocument, view: Literal["graph", "dag"] = "graph") -> str:
    by_id = {n.id: n for n in doc.nodes}
    ids, rows = edge_rows(doc, view)
    alias = {nid: f"n{i}" for i, nid in enumerate(ids)}
    lines = ["flowchart LR"]
    for nid in ids:
        n = by_id[nid]
        left, right = SHAPES[n.type]
        lines.append(f"    {alias[nid]}{left}{_q(n.label)}{right}:::{n.type}")
    for r in rows:
        if r.source in alias and r.target in alias:
            arrow = "-->" if r.status == "EXTRACTED" else "-.->"
            lines.append(f"    {alias[r.source]} {arrow}|{_q(r.label)}| {alias[r.target]}")
    for t, style in CLASSES.items():
        lines.append(f"    classDef {t} {style}")
    return "\n".join(lines) + "\n"
