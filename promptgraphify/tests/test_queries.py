"""The eight named queries on one prompt whose answers are derived by hand (see the comments)."""

import pytest

from promptgraphify.analyze import analyze
from promptgraphify.queries import QUERY_NAMES, QUERY_SPECS, explain_node, run_query

PROMPT = """# Support pipeline

## Agent: Planner
You are the planner agent.
Extract the order id from {{ticket}}.
Pass the order id to the Researcher.

## Agent: Researcher
You are the researcher agent.
Look up the order with the order_lookup tool.
Never share customer emails.

## Tools
- order_lookup(id): finds an order

## Variables
- ticket: the raw support ticket
- spare: not used anywhere
"""


@pytest.fixture(scope="module")
def doc():
    return analyze({"prompt.md": PROMPT})


def labels(result):
    return [r.title for r in result.rows]


def test_there_are_exactly_eight_named_queries_with_questions_and_definitions():
    assert len(QUERY_SPECS) == 8 and len(set(QUERY_NAMES)) == 8
    for q in QUERY_SPECS:
        assert q.question and q.definition and q.title


def test_task_context(doc):
    r = run_query(doc, "task_context", {"task": "Extract the order id"})
    assert r.status == "ok" and labels(r) == ["ticket"] and r.rows[0].basis == "explicit"
    assert "{{ticket}}" in r.rows[0].evidence[0].text


def test_constraints_on_tasks(doc):
    r = run_query(doc, "constraints_on_tasks")
    assert r.status == "ok" and len(r.rows) == 1
    row = r.rows[0]
    assert row.title == "Never share customer emails." and row.basis == "inferred"
    assert any("order_lookup tool" in doc_node.original_text for doc_node in doc.nodes if doc_node.id in row.node_ids)
    focused = run_query(doc, "constraints_on_tasks", {"task": "Extract the order id"})
    assert focused.rows == []  # that task is in another agent's section


def test_agent_tools(doc):
    r = run_query(doc, "agent_tools")
    assert labels(r) == ["Researcher"] and "order_lookup" in r.rows[0].detail and r.rows[0].basis == "explicit"


def test_unused_variables(doc):
    assert labels(run_query(doc, "unused_variables")) == ["spare"]


def test_shortest_path_directed_undirected_and_no_path(doc):
    r = run_query(doc, "shortest_path", {"source": "Pass the order id", "target": "order_lookup"})
    assert r.status == "ok" and len(r.paths[0]) == 3 and "2 hop" in r.summary
    assert [row.detail.split(" ")[0] for row in r.rows] == ["PRECEDES", "CALLS_TOOL"]
    back = run_query(doc, "shortest_path", {"source": "order_lookup", "target": "Pass the order id"})
    assert back.status == "no_path" and "undirected=true" in back.summary
    und = run_query(
        doc, "shortest_path", {"source": "order_lookup", "target": "Pass the order id", "undirected": "true"}
    )
    assert und.status == "ok" and und.paths[0][0].startswith("tool:") and "←" in und.rows[0].title
    assert run_query(doc, "shortest_path", {"source": "order_lookup", "target": "order_lookup"}).status == "invalid"


def test_execution_bottleneck(doc):
    r = run_query(doc, "execution_bottleneck")
    assert r.status == "ok" and "No single vertex" in r.summary  # lookup carries 1 of 2 paths: not more than half
    assert labels(r) == ["critical path"] and len(r.paths[0]) == 3  # pass -> lookup -> order_lookup


def test_execution_bottleneck_when_one_exists():
    d = analyze(
        {
            "p.md": (
                "1. Extract {{a}}.\n2. Extract {{b}}.\n3. Merge step 1 and step 2.\n"
                "4. Summarize step 3.\n5. Send step 3.\n"
            )
        }
    )
    r = run_query(d, "execution_bottleneck")
    # hand count: every one of the 6 source-to-sink paths passes through step 3 (share 100 %)
    assert r.rows[0].title.startswith("Merge") and "100%" in r.rows[0].detail


def test_conflicts():
    d = analyze({"p.md": "Always use formal language.\nNever use formal language.\nBe brief.\n"})
    r = run_query(d, "conflicts")
    assert len(r.rows) == 1 and r.rows[0].detail.startswith("probable conflict")
    assert run_query(analyze({"p.md": "Be brief.\n"}), "conflicts").rows == []


def test_most_dependent_ranking(doc):
    r = run_query(doc, "most_dependent", {"top": "3"})
    assert labels(r) == [
        "order_lookup",
        "Extract the order id from {{ticket}}.",
        "Look up the order with the order_lookup tool.",
    ]
    assert "2 transitive" in r.rows[0].detail and "1 direct" in r.rows[1].detail
    assert run_query(doc, "most_dependent", {"top": "x"}).status == "invalid"


def test_names_are_never_guessed(doc):
    r = run_query(doc, "task_context", {"task": "the order"})
    assert r.status == "ambiguous" and len(r.candidates) == 3 and r.rows == []
    assert run_query(doc, "task_context", {"task": "zebra"}).status == "not_found"
    assert run_query(doc, "task_context", {}).status == "invalid"
    assert run_query(doc, "nope").status == "invalid"
    only_task = run_query(doc, "task_context", {"task": "order_lookup"})  # a tool is not a task
    assert only_task.status in ("ok", "not_found")


def test_every_row_has_source_evidence(doc):
    for name, params in [
        ("task_context", {"task": "Extract the order id"}),
        ("constraints_on_tasks", {}),
        ("agent_tools", {}),
        ("unused_variables", {}),
        ("shortest_path", {"source": "Pass the order id", "target": "order_lookup"}),
        ("execution_bottleneck", {}),
        ("most_dependent", {}),
    ]:
        for row in run_query(doc, name, params).rows:
            assert row.evidence, f"{name}: row {row.title!r} has no evidence"
            for ev in row.evidence:
                assert PROMPT[ev.span.start : ev.span.end] == ev.text


def test_queries_are_deterministic(doc):
    other = analyze({"prompt.md": PROMPT})
    for name in QUERY_NAMES:
        params = {"task": "Extract the order id", "source": "Pass the order id", "target": "order_lookup"}
        a = run_query(doc, name, params).model_dump_json()
        assert a == run_query(other, name, params).model_dump_json() == run_query(doc, name, params).model_dump_json()


def test_explain_lists_every_relation_with_evidence(doc):
    r = explain_node(doc, "Look up the order")
    assert r.status == "ok" and r.rows[0].title.startswith("TaskNode")
    rels = {row.title.split(" ")[0] for row in r.rows[1:]}
    assert {"CALLS_TOOL", "PRECEDES", "CONSTRAINS"} <= rels
    assert explain_node(doc, "order").status == "ambiguous"
