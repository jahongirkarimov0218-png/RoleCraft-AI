"""The ontology is closed. Expectations here are written from the task text and ANALYSIS_SPEC §5/§6,
not read back from ontology.py."""

import pytest

from promptgraphify.ontology import (
    EDGE_STATUSES,
    NODE_TYPES,
    RELATION_TABLE,
    RELATIONS,
    TYPE_CODES,
    pair_allowed,
)

EXPECTED_TYPES = {
    "SystemNode",
    "TaskNode",
    "ContextNode",
    "ConstraintNode",
    "ToolNode",
    "ExampleNode",
}
EXPECTED_RELATIONS = {
    "DEPENDS_ON", "CONSTRAINS", "PROVIDES_CONTEXT", "CALLS_TOOL", "PRODUCES", "REFERENCES",
    "OVERRIDES", "CONFLICTS_WITH", "PRECEDES", "EXEMPLIFIES", "CONDITIONALLY_EXECUTES",
}  # fmt: skip


def test_exactly_six_node_types():
    assert set(NODE_TYPES) == EXPECTED_TYPES and len(NODE_TYPES) == 6


def test_exactly_eleven_relations():
    assert set(RELATIONS) == EXPECTED_RELATIONS and len(RELATIONS) == 11
    assert set(RELATION_TABLE) == EXPECTED_RELATIONS


def test_three_statuses():
    assert set(EDGE_STATUSES) == {"EXTRACTED", "INFERRED", "AMBIGUOUS"}


def test_type_codes_are_unique_and_complete():
    assert set(TYPE_CODES) == EXPECTED_TYPES
    assert len(set(TYPE_CODES.values())) == 6


@pytest.mark.parametrize(
    ("relation", "src", "tgt"),
    [
        ("DEPENDS_ON", "TaskNode", "ContextNode"),  # "which context does this task depend on?"
        ("DEPENDS_ON", "TaskNode", "TaskNode"),
        ("CONSTRAINS", "ConstraintNode", "TaskNode"),  # "which constraints affect which tasks?"
        ("CONSTRAINS", "ConstraintNode", "ToolNode"),
        ("CALLS_TOOL", "TaskNode", "ToolNode"),
        ("PRODUCES", "TaskNode", "ContextNode"),
        ("PRECEDES", "TaskNode", "TaskNode"),
        ("EXEMPLIFIES", "ExampleNode", "TaskNode"),
        ("PROVIDES_CONTEXT", "ContextNode", "TaskNode"),
        ("CONDITIONALLY_EXECUTES", "ContextNode", "TaskNode"),
        ("CONFLICTS_WITH", "ConstraintNode", "ConstraintNode"),
        ("OVERRIDES", "SystemNode", "ConstraintNode"),
        ("REFERENCES", "ExampleNode", "SystemNode"),
    ],
)
def test_allowed_pairs(relation, src, tgt):
    assert pair_allowed(relation, src, tgt)


@pytest.mark.parametrize(
    ("relation", "src", "tgt"),
    [
        ("CALLS_TOOL", "ToolNode", "TaskNode"),  # direction matters
        ("CALLS_TOOL", "TaskNode", "ContextNode"),
        ("DEPENDS_ON", "ConstraintNode", "TaskNode"),
        ("CONSTRAINS", "TaskNode", "ConstraintNode"),
        ("EXEMPLIFIES", "TaskNode", "ExampleNode"),
        ("PRECEDES", "TaskNode", "ToolNode"),
        ("PRODUCES", "ConstraintNode", "ContextNode"),
        ("CONFLICTS_WITH", "ToolNode", "TaskNode"),
        ("PROVIDES_CONTEXT", "TaskNode", "ContextNode"),
        ("NOT_A_RELATION", "TaskNode", "TaskNode"),
    ],
)
def test_forbidden_pairs(relation, src, tgt):
    assert not pair_allowed(relation, src, tgt)


def test_only_conflicts_with_is_symmetric():
    assert [r for r, s in RELATION_TABLE.items() if s.symmetric] == ["CONFLICTS_WITH"]


def test_conflict_is_never_extracted():
    assert "EXTRACTED" not in RELATION_TABLE["CONFLICTS_WITH"].allowed_status


def test_dag_projection_matches_spec():
    projected = {r: s.dag for r, s in RELATION_TABLE.items() if s.dag}
    assert projected == {
        "PRECEDES": "forward",
        "DEPENDS_ON": "reversed",  # opposite arrow to PRECEDES (ANALYSIS_SPEC §6)
        "CALLS_TOOL": "forward",
        "PRODUCES": "forward",
        "CONDITIONALLY_EXECUTES": "forward",
    }
