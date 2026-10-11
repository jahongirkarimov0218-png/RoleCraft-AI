"""Small hand-built documents for invariant tests. These construct IR directly; they do not use any
parser, so a test of the validator never depends on parser behaviour."""

from __future__ import annotations

import hashlib

from promptgraphify import __version__
from promptgraphify.coverage import compute_coverage
from promptgraphify.ids import edge_id
from promptgraphify.ir import Edge, Evidence, GraphDocument, Node, SourceFile, ToolInfo
from promptgraphify.spans import Span

FILE = "prompt.txt"


def source_file(text: str, path: str = FILE) -> SourceFile:
    return SourceFile(
        path=path,
        text=text,
        sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
        length=len(text),
    )


def find_span(text: str, quote: str, occurrence: int = 1) -> Span:
    idx = -1
    for _ in range(occurrence):
        idx = text.find(quote, idx + 1)
        assert idx >= 0, f"quote {quote!r} (occurrence {occurrence}) not found"
    return Span(start=idx, end=idx + len(quote))


def make_node(text: str, node_id: str, node_type: str, quote: str, occurrence: int = 1, **kw) -> Node:
    span = find_span(text, quote, occurrence)
    base = dict(
        id=node_id,
        type=node_type,
        label=quote[:60],
        description=f"{node_type} for tests",
        original_text=quote,
        source_file=FILE,
        source_span=span,
        metadata={"span_precision": "exact"},
        extraction_method="deterministic:test",
        confidence=1.0,
        validation_status="verified",
    )
    base.update(kw)
    return Node(**base)


def evidence(text: str, quote: str, occurrence: int = 1) -> Evidence:
    return Evidence(source_file=FILE, span=find_span(text, quote, occurrence), text=quote)


def make_edge(text: str, relation: str, source: str, target: str, quotes: list[str], **kw) -> Edge:
    base = dict(
        id=edge_id(relation, source, target),
        source=source,
        target=target,
        relation=relation,
        rationale="test edge",
        evidence=[evidence(text, q) for q in quotes],
        status="EXTRACTED",
        reference=quotes[0],
        extraction_method="deterministic:test",
        confidence=1.0,
    )
    base.update(kw)
    return Edge(**base)


def make_doc(text: str, nodes: list[Node], edges: list[Edge] | None = None, **kw) -> GraphDocument:
    cov = compute_coverage(FILE, text, [n.source_span for n in nodes], [])
    base = dict(
        tool=ToolInfo(version=__version__),
        analyzer_version=__version__,
        graph_id="test",
        sources=[source_file(text)],
        nodes=nodes,
        edges=edges or [],
        coverage=[cov],
    )
    base.update(kw)
    return GraphDocument(**base)


def codes(violations) -> set[str]:
    return {v.code for v in violations}
