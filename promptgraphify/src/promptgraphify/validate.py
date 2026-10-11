"""Layer C: graph invariants and provenance verification.

``validate_document`` never raises on a bad document; it returns every violation so a caller (CLI
``validate``, the API, tests) can show them all. ``assert_valid`` raises ``GraphInvalid`` for code that
must stop. A graph that fails here must not be rendered, exported or stored.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from .coverage import count_nonspace, intervals_overlap, merge_spans, nonspace_prefix
from .ir import SCHEMA_VERSION, Diagnostic, Edge, Evidence, GraphDocument, Node
from .ontology import RELATION_TABLE, pair_allowed
from .security import is_clean_label
from .spans import Span


@dataclass(frozen=True)
class Violation:
    code: str
    message: str
    subject: str | None = None

    def __str__(self) -> str:
        where = f" [{self.subject}]" if self.subject else ""
        return f"{self.code}{where}: {self.message}"


class GraphInvalid(ValueError):
    def __init__(self, violations: list[Violation]):
        self.violations = violations
        head = "\n".join(f"  - {v}" for v in violations[:20])
        more = f"\n  … and {len(violations) - 20} more" if len(violations) > 20 else ""
        super().__init__(f"graph has {len(violations)} violation(s):\n{head}{more}")


def verify_span(source: str, span: Span, text: str) -> str | None:
    """Return a problem description, or ``None`` if ``source[span] == text`` holds."""
    if span.end > len(source):
        return f"span [{span.start}, {span.end}) is outside the source ({len(source)} code points)"
    actual = source[span.start : span.end]
    if actual != text:
        return f"source[{span.start}:{span.end}] = {actual[:60]!r} but recorded text is {text[:60]!r}"
    return None


def validate_document(doc: GraphDocument) -> list[Violation]:
    out: list[Violation] = []
    if doc.schema_version != SCHEMA_VERSION:
        out.append(
            Violation(
                "schema.version",
                f"graph has schema_version {doc.schema_version!r}, this build reads {SCHEMA_VERSION!r}",
            )
        )
        return out  # nothing else can be trusted

    sources = {s.path: s for s in doc.sources}
    if len(sources) != len(doc.sources):
        out.append(Violation("source.duplicate", "two sources share a path"))
    for s in doc.sources:
        if len(s.text) != s.length:
            out.append(Violation("source.length", "length does not match text", s.path))

    nodes = _check_nodes(doc, sources, out)
    edges = _check_edges(doc, nodes, sources, out)
    _check_diagnostics(doc, nodes, edges, sources, out)
    _check_coverage(doc, sources, out)
    return out


def assert_valid(doc: GraphDocument) -> None:
    violations = validate_document(doc)
    if violations:
        raise GraphInvalid(violations)


# --------------------------------------------------------------------------------------------- nodes
def _check_nodes(doc: GraphDocument, sources: dict, out: list[Violation]) -> dict[str, Node]:
    by_id: dict[str, Node] = {}
    for n in doc.nodes:
        if n.id in by_id:
            out.append(Violation("node.duplicate_id", "node id is not unique", n.id))
        by_id[n.id] = n
        src = sources.get(n.source_file)
        if src is None:
            out.append(Violation("node.source_unknown", f"unknown source {n.source_file!r}", n.id))
        else:
            problem = verify_span(src.text, n.source_span, n.original_text)
            if problem:
                out.append(Violation("node.span_mismatch", problem, n.id))
            elif not n.original_text.strip():
                out.append(Violation("node.empty_text", "node covers only whitespace", n.id))
        if not is_clean_label(n.label):
            out.append(
                Violation(
                    "node.label_invalid",
                    f"label is empty, too long or unsafe: {n.label[:40]!r}",
                    n.id,
                )
            )
        if not n.description.strip():
            out.append(Violation("node.description_empty", "description is empty", n.id))
        if n.metadata.get("span_precision") not in ("exact", "enclosing"):
            out.append(
                Violation(
                    "node.span_precision",
                    "metadata.span_precision must be 'exact' or 'enclosing'",
                    n.id,
                )
            )
        if n.extraction_method.startswith("llm:") and n.confidence >= 1:
            out.append(Violation("node.llm_confidence", "LLM-proposed node cannot have confidence 1", n.id))
    return by_id


# --------------------------------------------------------------------------------------------- edges
def _check_edges(doc: GraphDocument, nodes: dict[str, Node], sources: dict, out: list[Violation]):
    by_id: dict[str, Edge] = {}
    for e in doc.edges:
        if e.id in by_id:
            out.append(Violation("edge.duplicate_id", "edge id is not unique", e.id))
        by_id[e.id] = e
        src, tgt = nodes.get(e.source), nodes.get(e.target)
        if src is None:
            out.append(Violation("edge.dangling_source", f"source {e.source!r} is not a node", e.id))
        if tgt is None:
            out.append(Violation("edge.dangling_target", f"target {e.target!r} is not a node", e.id))
        spec = RELATION_TABLE[e.relation]
        if src and tgt:
            if not pair_allowed(e.relation, src.type, tgt.type):
                out.append(
                    Violation(
                        "edge.relation_pair",
                        f"{e.relation} may not connect {src.type} -> {tgt.type}",
                        e.id,
                    )
                )
            if spec.symmetric and _order_key(src) > _order_key(tgt):
                out.append(
                    Violation(
                        "edge.symmetric_order",
                        "symmetric edge must start at the earlier span",
                        e.id,
                    )
                )
        if e.status not in spec.allowed_status:
            out.append(Violation("edge.status_not_allowed", f"{e.relation} cannot be {e.status}", e.id))
        if e.source == e.target and e.metadata.get("loop") is not True:
            out.append(Violation("edge.self_loop", "self-loop without metadata.loop = true", e.id))
        if not e.evidence:
            out.append(Violation("edge.evidence_empty", "every edge needs at least one evidence span", e.id))
        _check_evidence(e.evidence, sources, e.id, "edge", out)
        _check_status_rules(e, out)
    return by_id


def _order_key(n: Node) -> tuple:
    return (n.source_file, n.source_span.start, n.source_span.end, n.id)


def _check_status_rules(e: Edge, out: list[Violation]) -> None:
    if e.status == "EXTRACTED":
        if e.confidence != 1:
            out.append(Violation("edge.extracted_confidence", "EXTRACTED edges have confidence 1", e.id))
        if not e.reference:
            out.append(
                Violation(
                    "edge.extracted_without_reference",
                    "EXTRACTED edge has no explicit reference",
                    e.id,
                )
            )
        elif not any(e.reference in ev.text for ev in e.evidence):
            out.append(
                Violation(
                    "edge.extracted_reference_not_in_evidence",
                    f"reference {e.reference!r} does not occur in any evidence span",
                    e.id,
                )
            )
    elif e.status == "INFERRED":
        if not e.rule:
            out.append(Violation("edge.inferred_without_rule", "INFERRED edge must name its rule", e.id))
        if not e.confidence < 1:
            out.append(Violation("edge.inferred_confidence", "INFERRED edges have confidence < 1", e.id))
    else:  # AMBIGUOUS
        if not e.confidence < 1:
            out.append(Violation("edge.ambiguous_confidence", "AMBIGUOUS edges have confidence < 1", e.id))
    if e.extraction_method.startswith("llm:") and e.status == "EXTRACTED":
        out.append(Violation("edge.llm_extracted", "an LLM-proposed edge cannot be EXTRACTED", e.id))


def _check_evidence(
    items: list[Evidence], sources: dict, subject: str, kind: str, out: list[Violation]
) -> None:
    for ev in items:
        src = sources.get(ev.source_file)
        if src is None:
            out.append(
                Violation(f"{kind}.evidence_source_unknown", f"unknown source {ev.source_file!r}", subject)
            )
            continue
        problem = verify_span(src.text, ev.span, ev.text)
        if problem:
            out.append(Violation(f"{kind}.evidence_span_mismatch", problem, subject))


# ------------------------------------------------------------------------------------- diagnostics
def _check_diagnostics(doc, nodes, edges, sources, out: list[Violation]) -> None:
    seen: Counter[str] = Counter(d.id for d in doc.diagnostics)
    for d in doc.diagnostics:
        _check_one_diagnostic(d, nodes, edges, sources, seen, out)


def _check_one_diagnostic(d: Diagnostic, nodes, edges, sources, seen, out: list[Violation]) -> None:
    if seen[d.id] > 1:
        out.append(Violation("diag.duplicate_id", "diagnostic id is not unique", d.id))
    for nid in d.affected_nodes:
        if nid not in nodes:
            out.append(Violation("diag.unknown_node", f"affected node {nid!r} does not exist", d.id))
    for eid in d.affected_edges:
        if eid not in edges:
            out.append(Violation("diag.unknown_edge", f"affected edge {eid!r} does not exist", d.id))
    if d.detection in ("heuristic", "llm") and d.certainty == "proven":
        out.append(Violation("diag.certainty", "a heuristic/LLM finding cannot be 'proven'", d.id))
    if not d.suggested_fix.strip():
        out.append(Violation("diag.suggested_fix_empty", "suggested_fix is empty", d.id))
    _check_evidence(d.evidence, sources, d.id, "diag", out)


# ---------------------------------------------------------------------------------------- coverage
def _check_coverage(doc: GraphDocument, sources: dict, out: list[Violation]) -> None:
    cov_by_file = {c.source_file: c for c in doc.coverage}
    for path, src in sources.items():
        cov = cov_by_file.get(path)
        if cov is None:
            out.append(Violation("coverage.missing", "no coverage record for source", path))
            continue
        prefix = nonspace_prefix(src.text)
        total = prefix[-1]

        covered = merge_spans([n.source_span for n in doc.nodes if n.source_file == path])
        structural = merge_spans(cov.structural_spans)
        uncovered = merge_spans(cov.uncovered_spans)
        if cov.total != total:
            out.append(
                Violation(
                    "coverage.total",
                    f"total {cov.total} != {total} non-whitespace code points",
                    path,
                )
            )
        if (
            intervals_overlap(covered, structural)
            or intervals_overlap(covered, uncovered)
            or intervals_overlap(structural, uncovered)
        ):
            out.append(Violation("coverage.overlap", "covered / structural / uncovered spans overlap", path))
        c, s, u = (count_nonspace(prefix, m) for m in (covered, structural, uncovered))
        if (c, s, u) != (cov.covered, cov.structural, cov.uncovered):
            out.append(
                Violation(
                    "coverage.counts",
                    f"recorded {cov.covered}/{cov.structural}/{cov.uncovered} but spans give {c}/{s}/{u}",
                    path,
                )
            )
        if c + s + u != total:
            out.append(
                Violation(
                    "coverage.partition",
                    f"covered+structural+uncovered = {c + s + u}, total = {total}",
                    path,
                )
            )
