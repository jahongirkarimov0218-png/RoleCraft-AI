# ruff: noqa: E501
"""Standalone SVG of the knowledge graph or the execution DAG. All text is XML-escaped and stripped of
control characters; the file contains no script and no external reference."""

from __future__ import annotations

from dataclasses import dataclass
from html import escape as _escape
from typing import Literal

from ..dag import STATUS_RANK, project
from ..ir import GraphDocument
from ..ontology import RELATION_TABLE
from ..security import sanitize_label, xml_safe
from .layout import NODE_H, NODE_W, layered_layout

COLORS = {
    "SystemNode": "#8b6cf0", "TaskNode": "#2f7fe0", "ContextNode": "#14a578",
    "ConstraintNode": "#c78a00", "ToolNode": "#0f9fb5", "ExampleNode": "#d6459a",
}  # fmt: skip
SHORT = {
    "SystemNode": "SYSTEM",
    "TaskNode": "TASK",
    "ContextNode": "CONTEXT",
    "ConstraintNode": "CONSTRAINT",
    "ToolNode": "TOOL",
    "ExampleNode": "EXAMPLE",
}
CSS = """
.bg{fill:#fff}.node rect{fill:#fff;stroke-width:1.6}.node text{fill:#151922;font:12px system-ui,sans-serif}
.node .kind{font-size:9px;fill:#566074;letter-spacing:.05em}
.edge{fill:none;stroke:#151922;stroke-width:1.3}.edge.INFERRED{stroke:#566074;stroke-dasharray:6 4}
.edge.AMBIGUOUS{stroke:#a46f00;stroke-dasharray:2 4}.edge.loop{stroke-dasharray:1 3}
.elabel{fill:#566074;font:9px system-ui,sans-serif;text-anchor:middle}
@media (prefers-color-scheme:dark){.bg{fill:#0b0d12}.node rect{fill:#11141b}.node text{fill:#e6e9f0}.node .kind{fill:#98a1b6}
.edge{stroke:#e6e9f0}.edge.INFERRED{stroke:#98a1b6}.edge.AMBIGUOUS{stroke:#f3c04a}.elabel{fill:#98a1b6}}
"""


def escape(text: str, quote: bool = True) -> str:
    """XML/HTML escape after replacing characters XML 1.0 cannot carry (the file must stay well-formed)."""
    return _escape(xml_safe(text), quote=quote)


def arrow_label(relation: str, view: str) -> str:
    """Words for an arrow. In the DAG view arrows point from prerequisite to dependent, so a reversed
    relation (DEPENDS_ON: "source needs target") must not keep its own name."""
    if view == "dag" and RELATION_TABLE[relation].dag == "reversed":
        return "needed by"
    return relation.replace("_", " ").lower()


def _wrap(text: str, width: int = 26, lines: int = 2) -> list[str]:
    words, out, cur = text.split(" "), [], ""
    for w in words:
        if len(cur) + len(w) + 1 > width and cur:
            out.append(cur)
            cur = w
        else:
            cur = f"{cur} {w}".strip()
    out.append(cur)
    if len(out) > lines:
        out = [*out[: lines - 1], out[lines - 1][: width - 1] + "…"]
    return out


@dataclass(frozen=True)
class EdgeRow:
    source: str
    target: str
    status: str
    label: str
    loop: bool
    edge_id: str


def edge_rows(doc: GraphDocument, view: Literal["graph", "dag"]) -> tuple[list[str], list[EdgeRow]]:
    """Vertex ids and the arrows to draw. The DAG view draws one arrow per ordered pair (several
    knowledge-graph edges can project to the same pair): the most certain status wins, labels are joined."""
    if view == "graph":
        rows = [
            EdgeRow(e.source, e.target, e.status, arrow_label(e.relation, view), e.metadata.get("loop") is True, e.id)
            for e in doc.edges
        ]
        return [n.id for n in doc.nodes], rows
    ids, arrows, _ = project(doc.nodes, doc.edges)
    grouped: dict[tuple[str, str], list] = {}
    for a in arrows:
        grouped.setdefault((a.u, a.v), []).append(a.edge)
    rows = []
    for (u, v), group in sorted(grouped.items()):
        best = max(STATUS_RANK[e.status] for e in group)
        top = sorted((e for e in group if STATUS_RANK[e.status] == best), key=lambda e: e.id)
        labels = sorted({arrow_label(e.relation, view) for e in group})
        rows.append(EdgeRow(u, v, top[0].status, " + ".join(labels), False, top[0].id))
    return ids, rows


def graph_parts(doc: GraphDocument, view: Literal["graph", "dag"]):
    by_id = {n.id: n for n in doc.nodes}
    ids, edges = edge_rows(doc, view)
    order = {n.id: (n.source_file, n.source_span.start, n.id) for n in doc.nodes}
    pos, w, h = layered_layout(ids, [(r.source, r.target) for r in edges], order)
    return by_id, ids, edges, pos, w, h


def svg_body(doc: GraphDocument, view: Literal["graph", "dag"]) -> tuple[str, float, float]:
    by_id, ids, edges, pos, w, h = graph_parts(doc, view)
    out: list[str] = []
    for row in edges:
        src, tgt, status, loop, eid = row.source, row.target, row.status, row.loop, row.edge_id
        if src not in pos or tgt not in pos:
            continue
        (x1, y1), (x2, y2) = pos[src], pos[tgt]
        if src == tgt:
            d = f"M{x1 + NODE_W},{y1 + NODE_H / 2} c40,-30 40,{NODE_H} 0,{NODE_H / 2 - 4}"
            lx, ly = x1 + NODE_W + 30, y1 + NODE_H / 2
        else:
            sx, sy, tx, ty = x1 + NODE_W, y1 + NODE_H / 2, x2, y2 + NODE_H / 2
            if x2 <= x1:  # backwards edge: leave from the left side instead
                sx, tx = x1, x2 + NODE_W
            c = max(40.0, abs(tx - sx) / 2)
            d = f"M{sx},{sy} C{sx + (c if tx >= sx else -c)},{sy} {tx - (c if tx >= sx else -c)},{ty} {tx},{ty}"
            lx, ly = (sx + tx) / 2, (sy + ty) / 2 - 4
        cls = f"edge {status}{' loop' if loop else ''}"
        out.append(
            f'<path class="{cls}" data-edge-id="{escape(eid)}" d="{d}" marker-end="url(#arrow)"><title>{escape(row.label)} ({status})</title></path>'
        )
        if len(edges) <= 40:
            out.append(f'<text class="elabel" x="{lx:.0f}" y="{ly:.0f}">{escape(row.label)}</text>')
    for nid in ids:
        n = by_id[nid]
        x, y = pos[nid]
        color = COLORS[n.type]
        lines = _wrap(sanitize_label(n.label))
        tspans = "".join(
            f'<tspan x="{x + 10:.0f}" dy="{14 if i else 0}">{escape(line)}</tspan>' for i, line in enumerate(lines)
        )
        out.append(
            f'<g class="node" data-node-id="{escape(nid, quote=True)}" data-node-type="{n.type}" tabindex="0" role="button" aria-label="{escape(sanitize_label(n.type + " " + n.label), quote=True)}">'
            f"<title>{escape(sanitize_label(n.original_text))}</title>"
            f'<rect x="{x:.0f}" y="{y:.0f}" width="{NODE_W}" height="{NODE_H}" rx="6" stroke="{color}"/>'
            f'<text class="kind" x="{x + 10:.0f}" y="{y + 15:.0f}">{SHORT[n.type]}</text>'
            f'<text x="{x + 10:.0f}" y="{y + 31:.0f}">{tspans}</text></g>'
        )
    return "\n".join(out), w, h


def to_svg(doc: GraphDocument, view: Literal["graph", "dag"] = "graph") -> str:
    body, w, h = svg_body(doc, view)
    title = "Execution DAG" if view == "dag" else "Knowledge graph"
    return (
        f'<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w:.0f}" height="{h:.0f}" viewBox="0 0 {w:.0f} {h:.0f}" role="img" aria-label="{title}">\n'
        f"<title>{title} (graph {escape(doc.graph_id)})</title>\n<style>{CSS}</style>\n"
        '<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
        '<path d="M0,0 L10,5 L0,10 z" fill="#8a93a6"/></marker></defs>\n'
        f'<rect class="bg" width="100%" height="100%"/>\n{body}\n</svg>\n'
    )
