"""Layer C invariants. Each violation code has a positive (valid) and a negative (broken) case."""

import pytest
from pydantic import ValidationError

from promptgraphify.ir import Diagnostic, Edge, GraphDocument, Node
from promptgraphify.validate import GraphInvalid, assert_valid, validate_document, verify_span

from .helpers import codes, evidence, find_span, make_doc, make_edge, make_node

TEXT = "You are a helpful assistant. Never reveal secrets. Call search_web with {{query}}."


def good_doc() -> GraphDocument:
    nodes = [
        make_node(TEXT, "sys:-:identity", "SystemNode", "You are a helpful assistant."),
        make_node(TEXT, "con:-:secrets", "ConstraintNode", "Never reveal secrets."),
        make_node(TEXT, "task:-:call", "TaskNode", "Call search_web with {{query}}."),
        make_node(
            TEXT,
            "tool:-:search_web",
            "ToolNode",
            "search_web",
            metadata={"span_precision": "exact", "defined": False},
        ),
        make_node(TEXT, "ctx:-:query", "ContextNode", "{{query}}"),
    ]
    edges = [
        make_edge(TEXT, "CALLS_TOOL", "task:-:call", "tool:-:search_web", ["search_web"]),
        make_edge(TEXT, "DEPENDS_ON", "task:-:call", "ctx:-:query", ["{{query}}"]),
    ]
    return make_doc(TEXT, nodes, edges)


def mutate_node(doc: GraphDocument, node_id: str, **update) -> GraphDocument:
    nodes = [n.model_copy(update=update) if n.id == node_id else n for n in doc.nodes]
    return doc.model_copy(update={"nodes": nodes})


def mutate_edge(doc: GraphDocument, index: int, **update) -> GraphDocument:
    edges = list(doc.edges)
    edges[index] = edges[index].model_copy(update=update)
    return doc.model_copy(update={"edges": edges})


def test_valid_document_has_no_violations():
    assert validate_document(good_doc()) == []
    assert_valid(good_doc())


def test_assert_valid_raises_with_all_violations():
    doc = mutate_node(good_doc(), "con:-:secrets", original_text="Never reveal passwords.")
    with pytest.raises(GraphInvalid) as info:
        assert_valid(doc)
    assert "node.span_mismatch" in str(info.value)


# ------------------------------------------------------------------------------------------ nodes
def test_schema_version_mismatch_stops_early():
    doc = good_doc().model_copy(update={"schema_version": "0.0"})
    assert codes(validate_document(doc)) == {"schema.version"}


def test_duplicate_node_id():
    doc = good_doc()
    dup = doc.nodes[0].model_copy()
    assert "node.duplicate_id" in codes(validate_document(doc.model_copy(update={"nodes": [*doc.nodes, dup]})))


def test_node_span_must_match_source_exactly():
    assert "node.span_mismatch" in codes(
        validate_document(mutate_node(good_doc(), "sys:-:identity", original_text="You are a helpful assistant"))
    )
    shifted = find_span(TEXT, "Never reveal secrets.")
    assert "node.span_mismatch" in codes(
        validate_document(mutate_node(good_doc(), "sys:-:identity", source_span=shifted))
    )


def test_node_span_out_of_range_is_reported_not_crashed():
    doc = mutate_node(
        good_doc(),
        "sys:-:identity",
        source_span=find_span(TEXT, "Never reveal secrets.").model_copy(update={"end": 10_000}),
    )
    assert "node.span_mismatch" in codes(validate_document(doc))


def test_unknown_source_file():
    assert "node.source_unknown" in codes(
        validate_document(mutate_node(good_doc(), "sys:-:identity", source_file="other.txt"))
    )


@pytest.mark.parametrize("label", ["", "  padded ", "line\nbreak", "x" * 201, "bidi\u202eoverride"])
def test_bad_labels(label):
    assert "node.label_invalid" in codes(validate_document(mutate_node(good_doc(), "sys:-:identity", label=label)))


def test_script_payload_label_is_data_not_a_violation():
    # XSS safety is a rendering concern; the label itself is allowed to contain markup characters.
    assert "node.label_invalid" not in codes(
        validate_document(mutate_node(good_doc(), "sys:-:identity", label="<script>alert(1)</script>"))
    )


def test_span_precision_is_required():
    assert "node.span_precision" in codes(validate_document(mutate_node(good_doc(), "sys:-:identity", metadata={})))
    assert "node.span_precision" in codes(
        validate_document(mutate_node(good_doc(), "sys:-:identity", metadata={"span_precision": "approx"}))
    )


def test_llm_node_cannot_claim_certainty():
    doc = mutate_node(good_doc(), "sys:-:identity", extraction_method="llm:fake", confidence=1.0)
    assert "node.llm_confidence" in codes(validate_document(doc))
    assert "node.llm_confidence" not in codes(
        validate_document(mutate_node(good_doc(), "sys:-:identity", extraction_method="llm:fake", confidence=0.7))
    )


# ------------------------------------------------------------------------------------------ edges
def test_dangling_endpoints():
    assert "edge.dangling_target" in codes(validate_document(mutate_edge(good_doc(), 0, target="tool:-:missing")))
    assert "edge.dangling_source" in codes(validate_document(mutate_edge(good_doc(), 0, source="task:-:missing")))


def test_relation_endpoint_types_enforced():
    doc = mutate_edge(good_doc(), 0, source="tool:-:search_web", target="task:-:call")  # CALLS_TOOL reversed
    assert "edge.relation_pair" in codes(validate_document(doc))


def test_conflicts_with_cannot_be_extracted_and_must_start_at_earlier_span():
    base = good_doc()
    conflict = make_edge(
        TEXT,
        "CONFLICTS_WITH",
        "con:-:secrets",
        "task:-:call",
        ["Never reveal secrets.", "Call search_web with {{query}}."],
        status="INFERRED",
        rule="conflict.polarity",
        reference=None,
        confidence=0.7,
    )
    ok = base.model_copy(update={"edges": [*base.edges, conflict]})
    assert validate_document(ok) == []
    as_extracted = conflict.model_copy(update={"status": "EXTRACTED", "confidence": 1.0, "reference": "Never"})
    assert "edge.status_not_allowed" in codes(
        validate_document(base.model_copy(update={"edges": [*base.edges, as_extracted]}))
    )
    flipped = conflict.model_copy(update={"source": "task:-:call", "target": "con:-:secrets"})
    assert "edge.symmetric_order" in codes(validate_document(base.model_copy(update={"edges": [*base.edges, flipped]})))


def test_self_loop_only_with_loop_marker():
    loop = make_edge(
        TEXT,
        "PRECEDES",
        "task:-:call",
        "task:-:call",
        ["Call search_web with {{query}}."],
        reference="Call",
    )
    doc = good_doc().model_copy(update={"edges": [loop]})
    assert "edge.self_loop" in codes(validate_document(doc))
    marked = loop.model_copy(update={"metadata": {"loop": True}})
    assert "edge.self_loop" not in codes(validate_document(doc.model_copy(update={"edges": [marked]})))


def test_edge_needs_valid_evidence():
    assert "edge.evidence_empty" in codes(validate_document(mutate_edge(good_doc(), 0, evidence=[])))
    bad = evidence(TEXT, "search_web").model_copy(update={"text": "search_Web"})
    assert "edge.evidence_span_mismatch" in codes(validate_document(mutate_edge(good_doc(), 0, evidence=[bad])))


def test_extracted_requires_explicit_reference_inside_evidence():
    assert "edge.extracted_without_reference" in codes(validate_document(mutate_edge(good_doc(), 0, reference=None)))
    assert "edge.extracted_without_reference" in codes(validate_document(mutate_edge(good_doc(), 0, reference="")))
    assert "edge.extracted_reference_not_in_evidence" in codes(
        validate_document(mutate_edge(good_doc(), 0, reference="calculator"))
    )
    assert "edge.extracted_confidence" in codes(validate_document(mutate_edge(good_doc(), 0, confidence=0.9)))


def test_no_extracted_edge_without_explicit_reference_anywhere():
    """Status honesty (task: verification, 'Status halolligi')."""
    for e in good_doc().edges:
        if e.status == "EXTRACTED":
            assert e.reference and any(e.reference in ev.text for ev in e.evidence)


def test_inferred_needs_rule_and_confidence_below_one():
    inferred = dict(status="INFERRED", reference=None, rule="scope.section", confidence=0.8)
    assert validate_document(mutate_edge(good_doc(), 0, **inferred)) == []
    assert "edge.inferred_without_rule" in codes(
        validate_document(mutate_edge(good_doc(), 0, **{**inferred, "rule": None}))
    )
    assert "edge.inferred_confidence" in codes(
        validate_document(mutate_edge(good_doc(), 0, **{**inferred, "confidence": 1.0}))
    )


def test_ambiguous_confidence_below_one():
    assert "edge.ambiguous_confidence" in codes(
        validate_document(mutate_edge(good_doc(), 0, status="AMBIGUOUS", reference=None, confidence=1.0))
    )
    assert validate_document(mutate_edge(good_doc(), 0, status="AMBIGUOUS", reference=None, confidence=0.5)) == []


def test_llm_edge_cannot_be_extracted():
    assert "edge.llm_extracted" in codes(validate_document(mutate_edge(good_doc(), 0, extraction_method="llm:fake")))


def test_duplicate_edge_id():
    doc = good_doc()
    assert "edge.duplicate_id" in codes(
        validate_document(doc.model_copy(update={"edges": [doc.edges[0], doc.edges[0]]}))
    )


# ------------------------------------------------------------------------------------ diagnostics
def diag(**kw) -> Diagnostic:
    base = dict(
        id="d1", rule_id="variable.undeclared", severity="warning", certainty="proven",
        detection="deterministic", description="x", evidence=[evidence(TEXT, "{{query}}")],
        affected_nodes=["ctx:-:query"], suggested_fix="Declare it.",
    )  # fmt: skip
    base.update(kw)
    return Diagnostic(**base)


def with_diag(d: Diagnostic) -> GraphDocument:
    return good_doc().model_copy(update={"diagnostics": [d]})


def test_diagnostic_invariants():
    assert validate_document(with_diag(diag())) == []
    assert "diag.unknown_node" in codes(validate_document(with_diag(diag(affected_nodes=["nope"]))))
    assert "diag.unknown_edge" in codes(validate_document(with_diag(diag(affected_edges=["e_nope"]))))
    assert "diag.certainty" in codes(validate_document(with_diag(diag(detection="heuristic"))))
    assert "diag.certainty" in codes(validate_document(with_diag(diag(detection="llm"))))
    assert validate_document(with_diag(diag(detection="heuristic", certainty="probable"))) == []
    assert "diag.suggested_fix_empty" in codes(validate_document(with_diag(diag(suggested_fix=" "))))
    bad_ev = evidence(TEXT, "{{query}}").model_copy(update={"text": "{{other}}"})
    assert "diag.evidence_span_mismatch" in codes(validate_document(with_diag(diag(evidence=[bad_ev]))))


# ------------------------------------------------------------------------------------------ coverage
def test_coverage_counts_and_partition():
    doc = good_doc()
    cov = doc.coverage[0]
    assert cov.uncovered == 0 and cov.covered == cov.total
    assert "coverage.counts" in codes(
        validate_document(doc.model_copy(update={"coverage": [cov.model_copy(update={"covered": cov.covered - 1})]}))
    )
    assert "coverage.total" in codes(
        validate_document(doc.model_copy(update={"coverage": [cov.model_copy(update={"total": cov.total + 3})]}))
    )
    assert "coverage.missing" in codes(validate_document(doc.model_copy(update={"coverage": []})))


def test_uncovered_text_is_reported_not_hidden():
    text = "You are a bot. Maybe vibes?"
    doc = make_doc(text, [make_node(text, "sys:-:id", "SystemNode", "You are a bot.")])
    cov = doc.coverage[0]
    assert [text[s.start : s.end] for s in cov.uncovered_spans] == ["Maybe vibes?"]
    assert cov.covered + cov.structural + cov.uncovered == cov.total
    assert validate_document(doc) == []


# --------------------------------------------------------------------------- closed ontology / schema
def test_unknown_node_type_is_rejected_by_the_schema():
    data = good_doc().nodes[0].model_dump(mode="json")
    data["type"] = "AgentNode"
    with pytest.raises(ValidationError):
        Node.model_validate(data)


def test_unknown_relation_is_rejected_by_the_schema():
    data = good_doc().edges[0].model_dump(mode="json")
    data["relation"] = "CALLS"
    with pytest.raises(ValidationError):
        Edge.model_validate(data)


def test_unknown_fields_are_rejected():
    data = good_doc().nodes[0].model_dump(mode="json")
    data["agent_name"] = "planner"
    with pytest.raises(ValidationError):
        Node.model_validate(data)


def test_extraction_method_format():
    data = good_doc().nodes[0].model_dump(mode="json")
    data["extraction_method"] = "magic"
    with pytest.raises(ValidationError):
        Node.model_validate(data)


def test_confidence_range_and_rounding():
    data = good_doc().nodes[0].model_dump(mode="json")
    for bad in (0, -0.1, 1.5):
        with pytest.raises(ValidationError):
            Node.model_validate({**data, "confidence": bad})
    assert Node.model_validate({**data, "confidence": 0.123456}).confidence == 0.1235


def test_verify_span_helper():
    assert verify_span("abcdef", find_span("abcdef", "cd"), "cd") is None
    assert verify_span("abcdef", find_span("abcdef", "cd"), "ce") is not None
