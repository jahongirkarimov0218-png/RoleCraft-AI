"""The list of export formats, shared by the API (``GET /api/graph/{id}/export/{format}``) and the CLI."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal

from .. import graphjson
from ..ir import GraphDocument
from .graphml import to_graphml
from .html import to_html
from .mermaid import to_mermaid
from .report import to_report
from .svg import to_svg

View = Literal["graph", "dag"]


@dataclass(frozen=True)
class ExportFormat:
    name: str
    filename: str
    media_type: str
    description: str
    render: Callable[[GraphDocument, View], str]
    uses_view: bool = False  # True if the format can draw the execution DAG instead of the knowledge graph


def _json(doc: GraphDocument, view: View) -> str:
    return graphjson.dumps(doc)


def _html(doc: GraphDocument, view: View) -> str:
    return to_html(doc)


def _report(doc: GraphDocument, view: View) -> str:
    return to_report(doc)


def _graphml(doc: GraphDocument, view: View) -> str:
    return to_graphml(doc)


FORMATS: dict[str, ExportFormat] = {
    f.name: f
    for f in (
        ExportFormat("json", "graph.json", "application/json", "canonical graph document", _json),
        ExportFormat("html", "graph.html", "text/html", "offline interactive viewer (one file)", _html),
        ExportFormat("report", "GRAPH_REPORT.md", "text/markdown", "human-readable report", _report),
        ExportFormat("mermaid", "graph.mmd", "text/plain", "Mermaid flowchart", to_mermaid, True),
        ExportFormat("graphml", "graph.graphml", "application/graphml+xml", "GraphML (Gephi, yEd)", _graphml),
        ExportFormat("svg", "graph.svg", "image/svg+xml", "static SVG picture", to_svg, True),
    )
}


def render(name: str, doc: GraphDocument, view: View = "graph") -> tuple[ExportFormat, str]:
    """(format, text). ``KeyError`` for an unknown format name."""
    fmt = FORMATS[name]
    return fmt, fmt.render(doc, view)
