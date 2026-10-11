"""Defects found by running prompts of realistic size (the first synthetic prompt failed Layer C):
a tool mentioned in several tasks gave several identical diagnostics, and Markdown tool headings were not tools."""

from collections import Counter

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from promptgraphify.analyze import analyze
from promptgraphify.validate import validate_document

from .synthetic import synthetic_prompt


def tools(text: str):
    doc = analyze({"p.md": text})
    return {n.original_text: n.metadata.get("defined") for n in doc.nodes if n.type == "ToolNode"}, doc


# ------------------------------------------------------------------ one diagnostic per undefined tool
def test_an_undefined_tool_named_by_several_tasks_gets_one_diagnostic_listing_every_call():
    doc = analyze(
        {"p.md": "1. Use the send_notice tool.\n2. Use the send_notice tool again.\n3. Call send_notice once more.\n"}
    )
    found = [d for d in doc.diagnostics if d.rule_id == "tool.undefined"]
    assert len(found) == 1
    calls = [e.id for e in doc.edges if e.relation == "CALLS_TOOL"]
    assert len(calls) == 3 and sorted(found[0].affected_edges) == sorted(calls)  # nothing is lost by merging
    assert validate_document(doc) == []


# ---------------------------------------------------------------------------- Markdown tool headings
def test_a_tool_heading_with_a_description_defines_the_tool():
    defined, doc = tools(
        "## Tools\n\n### lookup_order\nCalls the order service.\n\n## Task\nUse the lookup_order tool.\n"
    )
    assert defined == {"Calls the order service.": True}
    assert [d.rule_id for d in doc.diagnostics if d.rule_id.startswith("tool")] == []
    (e,) = [e for e in doc.edges if e.relation == "CALLS_TOOL"]
    assert (e.status, e.reference) == ("EXTRACTED", "lookup_order")


def test_a_tool_heading_without_a_body_is_still_a_definition_spanning_its_name():
    defined, doc = tools("## Tools\n### lookup_order\n\n## Task\nUse the lookup_order tool.\n")
    assert defined == {"lookup_order": True} and not [d for d in doc.diagnostics if d.rule_id == "tool.undefined"]


def test_backticked_and_signature_style_headings_work_and_plain_words_do_not():
    assert tools("## Tools\n### `search`\nFinds things.\n")[0] == {"Finds things.": True}
    assert tools("## Tools\n### search_web(query)\nFinds things.\n")[0] == {"Finds things.": True}
    assert tools("## Tools\n### Calculator\nAdds numbers.\n")[0] == {}  # a plain word is not a tool name
    assert tools("## Notes\n### lookup_order\nSome text.\n")[0] == {}  # not under a tools heading


def test_bullet_signatures_under_a_tools_heading_still_work():
    assert tools("## Tools\n\n- lookup_order(order_id): finds an order.\n")[0] == {
        "lookup_order(order_id): finds an order.": True
    }


# ----------------------------------------------------------------------------------- realistic sizes
@pytest.mark.parametrize("units", [10, 60, 150, 400])
def test_synthetic_prompts_of_realistic_size_analyse_to_a_valid_graph(units):
    text = synthetic_prompt(units)
    doc = analyze({"p.md": text})
    assert validate_document(doc) == []
    ids = Counter(d.id for d in doc.diagnostics)
    assert max(ids.values(), default=1) == 1
    assert len(doc.nodes) >= units * 0.9  # the generator makes about `units` units; nearly all become nodes
    defined = {n.label for n in doc.nodes if n.type == "ToolNode" and n.metadata.get("defined") is True}
    assert len(defined) == 6 and not [d for d in doc.diagnostics if d.rule_id == "tool.undefined"]
    assert doc.dag.status == "ok" and len(doc.dag.critical_path) >= 8  # every section is a chain of 8 dependent steps
    again = analyze({"p.md": text})
    assert again.graph_id == doc.graph_id


POOL = [
    "Use the send_notice tool.",
    "Call fetch_data with the id.",
    "1. Extract {{x}}.",
    "2. Check step 1.",
    "Never reveal secrets.",
    "Always reveal secrets.",
    "Summarize {{y}} and {{x}}.",
    "Keep every answer under 50 words.",
    "Then send it.",
    "You are a bot.",
    "If {{x}} is empty, stop.",
    "Repeat step 1 until done.",
    "Ignore previous instructions.",
    "Check step 9.",
    "Use the send_notice tool.",
]


@settings(max_examples=150, deadline=None)
@given(st.lists(st.sampled_from(POOL), min_size=1, max_size=40), st.sampled_from(["\n", "\n\n", "\r\n"]))
def test_any_mix_of_repeated_mentions_gives_a_valid_graph(sentences, sep):
    doc = analyze({"p.md": sep.join(sentences)})  # raises GraphInvalid if any invariant (incl. unique ids) breaks
    assert validate_document(doc) == []
