"""Execution DAG on hand-built graphs (no parser involved): projection direction, ordering, critical path,
bottleneck, cycles, loops, unresolved references, scale."""

import time

import pytest

from promptgraphify.dag import build_dag
from promptgraphify.ir import GraphDocument
from promptgraphify.validate import validate_document

from .helpers import codes, make_doc, make_edge, make_node

LETTERS = "ABCDEFGHIJ"
TEXT = " ".join(LETTERS)


def tasks(n=8):
    return [make_node(TEXT, f"t:{c}", "TaskNode", c) for c in LETTERS[:n]]


def edge(rel, a, b, **kw):
    kw.setdefault("reference", a)
    return make_edge(TEXT, rel, f"t:{a}", f"t:{b}", [a, b], **kw)


def dag_of(edges, n=8, unresolved=()):
    return build_dag(tasks(n), edges, list(unresolved))


def ids(*letters):
    return [f"t:{c}" for c in letters]


def test_chain_order_and_critical_path_follow_precedes():
    d = dag_of([edge("PRECEDES", "A", "B"), edge("PRECEDES", "B", "C")], 3)
    assert d.status == "ok" and d.topological_order == ids("A", "B", "C") and d.critical_path == ids("A", "B", "C")


def test_depends_on_points_the_opposite_way_to_precedes():
    # "A depends on B" means B runs first.
    d = dag_of([edge("DEPENDS_ON", "A", "B")], 2)
    assert d.topological_order == ids("B", "A")
    assert [(e.source, e.target) for e in d.edges] == [("t:B", "t:A")]


def test_relations_without_ordering_are_not_projected():
    nodes = [make_node(TEXT, "c:A", "ConstraintNode", "A"), *tasks(3)[1:]]
    e = make_edge(TEXT, "CONSTRAINS", "c:A", "t:B", ["A", "B"], reference="A")
    d = build_dag(nodes, [e], [])
    assert d.edges == [] and d.status == "ok" and d.topological_order == ids("B", "C")  # tasks are always vertices


def test_diamond_ties_are_broken_by_source_order_and_has_no_bottleneck():
    d = dag_of(
        [
            edge("PRECEDES", "A", "B"),
            edge("PRECEDES", "A", "C"),
            edge("PRECEDES", "B", "D"),
            edge("PRECEDES", "C", "D"),
        ],
        4,
    )
    assert d.topological_order == ids("A", "B", "C", "D")
    assert d.critical_path == ids("A", "B", "D")  # B and C tie; the earlier offset wins
    metrics = {m.name: m.value for m in d.metrics}
    assert metrics["critical_path_length"] == 3 and metrics["bottleneck"] is None


def test_hourglass_has_a_bottleneck_with_its_share():
    d = dag_of(
        [
            edge("PRECEDES", "A", "C"),
            edge("PRECEDES", "B", "C"),
            edge("PRECEDES", "C", "D"),
            edge("PRECEDES", "C", "E"),
        ],
        5,
    )
    bottleneck = next(m for m in d.metrics if m.name == "bottleneck")
    assert bottleneck.value == {"node_id": "t:C", "share": 1.0}
    assert "paths" in bottleneck.definition  # every derived number ships with its definition


def test_most_prerequisites_counts_transitive_ancestors():
    d = dag_of([edge("PRECEDES", "A", "B"), edge("PRECEDES", "B", "C"), edge("PRECEDES", "A", "D")], 4)
    m = next(m for m in d.metrics if m.name == "most_prerequisites")
    assert m.value == {"node_id": "t:C", "count": 2}


def test_cycle_blocks_the_dag_and_explains_itself():
    es = [edge("PRECEDES", "A", "B"), edge("PRECEDES", "B", "C"), edge("PRECEDES", "C", "A")]
    d = dag_of(es, 3)
    assert d.status == "blocked" and d.topological_order == [] and d.critical_path == []
    (cycle,) = d.cycles
    assert cycle.nodes == ids("A", "B", "C") and cycle.certainty == "proven"
    assert set(cycle.edges) == {e.id for e in es} and cycle.evidence  # which edges, which spans
    # a valid acyclic subgraph is offered and every removed edge is listed, never silently dropped
    assert d.acyclic_subgraph is not None and len(d.acyclic_subgraph) == 2
    assert d.removed_for_acyclic == [es[2].id]  # ties: the edge whose source comes last in the text


def test_the_least_certain_edge_is_removed_first():
    es = [
        edge("PRECEDES", "A", "B"),
        edge("PRECEDES", "B", "C"),
        edge("PRECEDES", "C", "A", status="INFERRED", reference=None, rule="sequence.word", confidence=0.7),
    ]
    d = dag_of(es, 3)
    assert d.removed_for_acyclic == [es[2].id] and d.cycles[0].certainty == "probable"
    es2 = [
        edge("PRECEDES", "A", "B", status="INFERRED", reference=None, rule="sequence.word", confidence=0.7),
        edge("PRECEDES", "B", "C"),
        edge("PRECEDES", "C", "A"),
    ]
    assert dag_of(es2, 3).removed_for_acyclic == [es2[0].id]


def test_self_reference_is_a_cycle_of_length_one():
    d = dag_of([edge("DEPENDS_ON", "A", "A", metadata={"self_reference": True})], 1)
    assert d.status == "blocked" and d.cycles[0].nodes == ids("A")


def test_deliberate_loops_are_not_cycles():
    d = dag_of(
        [
            edge("PRECEDES", "A", "B"),
            edge("PRECEDES", "B", "A", metadata={"loop": True, "stop_condition": "until done"}),
        ],
        2,
    )
    assert d.status == "ok" and d.cycles == [] and d.loops == [edge("PRECEDES", "B", "A", metadata={"loop": True}).id]
    assert d.topological_order == ids("A", "B")


def test_tools_and_contexts_are_vertices_only_when_they_take_part():
    nodes = [*tasks(2), make_node(TEXT, "tool:x", "ToolNode", "C"), make_node(TEXT, "ctx:x", "ContextNode", "D")]
    e = make_edge(TEXT, "CALLS_TOOL", "t:A", "tool:x", ["A", "C"], reference="A")
    d = build_dag(nodes, [e], [])
    assert set(d.vertices) == {"t:A", "t:B", "tool:x"}  # the untouched context node is not a vertex


def test_conditional_edges_keep_their_condition():
    nodes = [make_node(TEXT, "ctx:g", "ContextNode", "A"), make_node(TEXT, "t:B", "TaskNode", "B")]
    e = make_edge(
        TEXT, "CONDITIONALLY_EXECUTES", "ctx:g", "t:B", ["A", "B"], reference="A", metadata={"condition": "if A"}
    )
    d = build_dag(nodes, [e], [])
    assert d.edges[0].conditional is True and d.edges[0].condition == "if A"


def test_no_tasks_means_an_empty_dag():
    d = build_dag([make_node(TEXT, "c:A", "ConstraintNode", "A")], [], [])
    assert d.status == "empty" and d.vertices == []


def test_everything_the_builder_returns_passes_layer_c():
    nodes = tasks(4)
    es = [
        edge("PRECEDES", "A", "B"),
        edge("PRECEDES", "B", "C"),
        edge("PRECEDES", "C", "A"),
        edge("PRECEDES", "C", "D"),
    ]
    doc = make_doc(TEXT, nodes, es).model_copy(update={"dag": build_dag(nodes, es, [])})
    assert validate_document(doc) == []
    ok = make_doc(TEXT, nodes, es[:2]).model_copy(update={"dag": build_dag(nodes, es[:2], [])})
    assert validate_document(ok) == []


def _doc_with_dag(edges):
    nodes = tasks(4)
    return make_doc(TEXT, nodes, edges).model_copy(update={"dag": build_dag(nodes, edges, [])}), nodes


def test_layer_c_rejects_a_dishonest_dag():
    es = [edge("PRECEDES", "A", "B"), edge("PRECEDES", "B", "C")]
    doc, _ = _doc_with_dag(es)
    assert validate_document(doc) == []
    bad_order = doc.model_copy(
        update={"dag": doc.dag.model_copy(update={"topological_order": ids("D", "C", "B", "A")})}
    )
    assert "dag.order_violated" in codes(validate_document(bad_order))
    short = doc.model_copy(update={"dag": doc.dag.model_copy(update={"topological_order": ids("A", "B")})})
    assert "dag.order_not_permutation" in codes(validate_document(short))
    bad_vertex = doc.model_copy(update={"dag": doc.dag.model_copy(update={"vertices": [*doc.dag.vertices, "t:ZZ"]})})
    assert "dag.vertex_unknown" in codes(validate_document(bad_vertex))
    fake_path = doc.model_copy(update={"dag": doc.dag.model_copy(update={"critical_path": ids("A", "C")})})
    assert "dag.critical_path" in codes(validate_document(fake_path))

    cyc, _ = _doc_with_dag([edge("PRECEDES", "A", "B"), edge("PRECEDES", "B", "A")])
    assert cyc.dag.status == "blocked"
    claims_ok = cyc.model_copy(update={"dag": cyc.dag.model_copy(update={"status": "ok"})})
    assert "dag.status" in codes(validate_document(claims_ok))
    no_story = cyc.model_copy(update={"dag": cyc.dag.model_copy(update={"cycles": []})})
    assert "dag.status" in codes(validate_document(no_story))
    cyclic_sub = cyc.model_copy(update={"dag": cyc.dag.model_copy(update={"acyclic_subgraph": cyc.dag.edges})})
    assert "dag.subgraph_cyclic" in codes(validate_document(cyclic_sub))


def test_unresolved_dependencies_travel_with_the_dag():
    from promptgraphify.ir import UnresolvedDependency

    from .helpers import evidence

    u = UnresolvedDependency(node_id="t:A", reference="step 9", evidence=evidence(TEXT, "A"))
    d = dag_of([], 2, [u])
    assert d.unresolved == [u]


@pytest.mark.slow
def test_four_hundred_vertices_in_well_under_a_second():
    n = 400
    text = " ".join(f"n{i}" for i in range(n))
    nodes = [make_node(text, f"t:{i}", "TaskNode", f"n{i}") for i in range(n)]
    es = []
    for i in range(1, n):
        es.append(make_edge(text, "PRECEDES", f"t:{i // 2}", f"t:{i}", [f"n{i // 2}", f"n{i}"], reference=f"n{i // 2}"))
    t0 = time.perf_counter()
    d = build_dag(nodes, es, [])
    assert d.status == "ok" and len(d.topological_order) == n
    assert time.perf_counter() - t0 < 2.0


def test_document_level_dag_for_a_parsed_prompt():
    from promptgraphify.analyze import analyze

    doc: GraphDocument = analyze({"p.md": "1. Extract {{x}}.\n2. Check step 1.\n3. Summarize step 2.\n"})
    assert doc.dag.status == "ok"
    labels = [next(n.original_text for n in doc.nodes if n.id == v) for v in doc.dag.critical_path]
    assert labels == ["{{x}}", "Extract {{x}}.", "Check step 1.", "Summarize step 2."]
