"""Public entry point of the core library: ``analyze(sources) -> GraphDocument``.

Pipeline: scan + extract per source (Layer A) -> link (edges) -> IDs -> IR -> coverage -> Layer C.
Everything is a pure function of (sources, config, analyzer version); there is no clock, no randomness
and no network, so the same input always gives byte-identical ``graph.json``.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping

from . import __version__
from .coverage import compute_coverage
from .extract import Draft, SourceData, extract_source
from .ids import disambiguate, edge_id, named_key, node_id, text_key
from .ir import (
    SCHEMA_VERSION,
    AnalysisConfig,
    Edge,
    Evidence,
    GraphDocument,
    Node,
    RoleScope,
    SourceFile,
    ToolInfo,
    empty_dag,
)
from .ontology import RELATIONS
from .relations import DraftEdge, Linked, link
from .security import sanitize_label
from .spans import Span
from .validate import assert_valid

LABEL_CHARS = 80
DEFAULT_MAX_INPUT_CHARS = 500_000
TYPE_ORDER = {
    t: i for i, t in enumerate(("SystemNode", "TaskNode", "ContextNode", "ConstraintNode", "ToolNode", "ExampleNode"))
}


class AnalysisError(ValueError):
    """The input cannot be analysed (limits, bad path); never raised for merely odd prompt content."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def _newline_style(text: str) -> str:
    crlf = text.count("\r\n")
    lf = text.count("\n") - crlf
    cr = text.count("\r") - crlf
    kinds = [k for k, n in (("crlf", crlf), ("lf", lf), ("cr", cr)) if n]
    return "none" if not kinds else kinds[0] if len(kinds) == 1 else "mixed"


def _source_file(path: str, text: str) -> SourceFile:
    return SourceFile(
        path=path,
        text=text,
        sha256=hashlib.sha256(text.encode("utf-8", "surrogatepass")).hexdigest(),
        length=len(text),
        has_bom=text.startswith("\N{ZERO WIDTH NO-BREAK SPACE}"),
        newline=_newline_style(text),
    )


def compute_graph_id(sources: list[tuple[str, str]], config: AnalysisConfig, analyzer_version: str) -> str:
    payload = json.dumps(
        {"sources": sources, "config": config.model_dump(mode="json"), "analyzer": analyzer_version},
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8", "surrogatepass")).hexdigest()[:16]


def _label(d: Draft) -> str:
    if d.name and d.type in ("ContextNode", "ToolNode"):
        return sanitize_label(d.name)
    text = sanitize_label(d.text)
    return text if len(text) <= LABEL_CHARS else text[: LABEL_CHARS - 1].rstrip() + "…"


def _jsonable(value):
    if isinstance(value, dict):
        return {str(k): _jsonable(v) for k, v in value.items() if not str(k).startswith("_")}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_jsonable(v) for v in value]
    return value


def _assign_ids(drafts: list[Draft], multi: bool) -> dict[int, str]:
    bases: list[str] = []
    for d in drafts:
        if d.name and d.type in ("ContextNode", "ToolNode"):
            bases.append(node_id(d.type, [], named_key(d.name)))
        else:
            stem = d.file.rsplit("/", 1)[-1].rsplit(".", 1)[0]
            path = ([stem] if multi else []) + d.section_path()
            bases.append(node_id(d.type, path, text_key(d.text)))
    return {id(d): nid for d, nid in zip(drafts, disambiguate(bases), strict=True)}


def _node(d: Draft, nid: str) -> Node:
    meta = _jsonable(d.meta)
    meta["section_path"] = d.section_path()
    meta["span_precision"] = d.precision
    return Node(
        id=nid,
        type=d.type,
        label=_label(d),
        description=d.description,
        original_text=d.text,
        decoded_text=d.decoded,
        source_file=d.file,
        source_span=Span(start=d.span[0], end=d.span[1]),
        role_scope=RoleScope(role=d.role, agent=d.agent),
        metadata=meta,
        extraction_method=f"deterministic:{d.rule}",
        confidence=d.confidence,
        validation_status="unverified",
    )


def _evidence(sources: dict[str, str], items) -> list[Evidence]:
    out, seen = [], set()
    for file, (a, b) in items:
        if (file, a, b) in seen:
            continue
        seen.add((file, a, b))
        out.append(Evidence(source_file=file, span=Span(start=a, end=b), text=sources[file][a:b]))
    return out


def _edges(linked: Linked, ids: dict[int, str], texts: dict[str, str]) -> list[Edge]:
    ordinal: dict[tuple, int] = {}
    out: list[Edge] = []
    for e in sorted(linked.edges, key=_edge_sort(ids)):
        src, tgt = ids[id(e.source)], ids[id(e.target)]
        n = ordinal[(e.relation, src, tgt)] = ordinal.get((e.relation, src, tgt), 0) + 1
        out.append(
            Edge(
                id=edge_id(e.relation, src, tgt, n),
                source=src,
                target=tgt,
                relation=e.relation,
                rationale=e.rationale,
                evidence=_evidence(texts, e.evidence),
                status=e.status,
                reference=e.reference,
                rule=e.rule,
                extraction_method=e.method,
                metadata=_jsonable(e.meta),
                confidence=e.confidence,
            )
        )
    return out


def _edge_sort(ids: dict[int, str]):
    def key(e: DraftEdge):
        return (
            RELATIONS.index(e.relation),
            ids[id(e.source)],
            ids[id(e.target)],
            e.evidence[0][1] if e.evidence else (0, 0),
        )

    return key


def analyze(
    inputs: Mapping[str, str] | list[tuple[str, str]],
    config: AnalysisConfig | None = None,
    *,
    max_input_chars: int = DEFAULT_MAX_INPUT_CHARS,
) -> GraphDocument:
    """Analyse ``inputs`` ({path: text}). ``max_input_chars`` is a runtime guard, not part of the result."""
    config = config or AnalysisConfig(layer_b=False)
    pairs = sorted(dict(inputs).items() if isinstance(inputs, Mapping) else inputs)
    if not pairs:
        raise AnalysisError("no_input", "no input files")
    if sum(len(t) for _, t in pairs) > max_input_chars:
        raise AnalysisError("input_too_large", f"input exceeds {max_input_chars} characters")
    if len({p for p, _ in pairs}) != len(pairs):
        raise AnalysisError("duplicate_path", "two inputs share a path")

    sources: list[SourceData] = [extract_source(p, t) for p, t in pairs]
    texts = {p: t for p, t in pairs}
    linked = link(sources)
    drafts = sorted(linked.drafts, key=lambda d: (d.file, d.span[0], -d.span[1], TYPE_ORDER[d.type]))
    ids = _assign_ids(drafts, multi=len(pairs) > 1)
    nodes = [_node(d, ids[id(d)]) for d in drafts]
    edges = _edges(linked, ids, texts)

    coverage = []
    for s in sources:
        spans = [n.source_span for n in nodes if n.source_file == s.path]
        coverage.append(compute_coverage(s.path, s.text, spans, [Span(start=a, end=b) for a, b in s.structural]))

    doc = GraphDocument(
        schema_version=SCHEMA_VERSION,
        tool=ToolInfo(version=__version__),
        analyzer_version=__version__,
        graph_id=compute_graph_id(pairs, config, __version__),
        config=config,
        sources=[_source_file(p, t) for p, t in pairs],
        nodes=nodes,
        edges=edges,
        coverage=coverage,
        diagnostics=[],
        dag=empty_dag(),
        warnings=[],
    )
    assert_valid(doc)
    return doc.model_copy(update={"nodes": [n.model_copy(update={"validation_status": "verified"}) for n in doc.nodes]})
