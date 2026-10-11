"""YAML / JSON front-ends: exact raw spans with escapes, block scalars, CRLF, emoji, hostile documents."""

import json

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from promptgraphify.analyze import analyze
from promptgraphify.docnode import DNode
from promptgraphify.jsonscan import scan_json
from promptgraphify.structured import detect_format
from promptgraphify.validate import validate_document
from promptgraphify.yamlscan import align, scan_yaml


def nodes_by_type(doc):
    out = {}
    for n in doc.nodes:
        out.setdefault(n.type, []).append(n)
    return out


def check_spans(doc, files):
    assert validate_document(doc) == []
    for n in doc.nodes:
        assert files[n.source_file][n.source_span.start : n.source_span.end] == n.original_text


# ------------------------------------------------------------------------------------------- JSON scanner
def test_json_scanner_decodes_escapes_with_exact_offsets():
    text = r'{"k": "aé\n\"b\" 😀 z"}'
    root, notes = scan_json(text)
    assert notes == []
    s = root.items[0][1]
    assert s.value == 'aé\n"b" \U0001f600 z'
    # every decoded character maps to the raw text that produced it
    pieces = [text[a:b] for a, b in zip(s.map_start, s.map_end, strict=True)]
    assert pieces[:3] == ["a", r"é", r"\n"]
    assert r"😀" in pieces and "".join(pieces) == text[s.start + 1 : s.end - 1]


@pytest.mark.parametrize(
    "bad",
    [
        '{"a": "x",}',
        '{"a": "x" // c\n}',
        '{"a": "unterminated',
        '{"a": [1, 2',
        '{a: "bare key"}',
        '{"a" "b"}',
        "[1,,2]",
        "}{",
        '"\\q"',
    ],
)
def test_json_scanner_never_raises_on_broken_input(bad):
    root, notes = scan_json(bad)
    assert isinstance(notes, list)  # recovered, with or without a tree


def test_json_depth_is_bounded():
    root, notes = scan_json("[" * 5000 + "]" * 5000)
    assert any("too deep" in n.message for n in notes)


# ------------------------------------------------------------------------------------------ JSON prompts
def test_json_messages_spans_decoded_view_and_roles():
    text = (
        '{"messages": [{"role": "system", "content": "You are a bot.\\nSay \\"hi\\" first."}, '
        '{"role": "user", "content": "Summarize {{doc}}."}]}'
    )
    doc = analyze({"p.json": text})
    check_spans(doc, {"p.json": text})
    by = {n.original_text: n for n in doc.nodes}
    assert by["You are a bot."].role_scope.role == "system"
    task = by[r"Say \"hi\" first."]
    assert task.decoded_text == 'Say "hi" first.' and task.metadata["span_precision"] == "exact"
    assert by["Summarize {{doc}}."].role_scope.role == "user"


def test_json_unicode_escapes_and_emoji_keep_code_point_offsets():
    text = '{"system": "You are \\u00e9l\\u00e8ve \\ud83d\\ude00. Never lie \\ud83d\\ude00."}'
    doc = analyze({"p.json": text})
    check_spans(doc, {"p.json": text})
    con = nodes_by_type(doc)["ConstraintNode"][0]
    assert con.original_text == "Never lie \\ud83d\\ude00." and con.decoded_text == "Never lie \U0001f600."


def test_json_tools_array_openai_style_and_variables_and_examples():
    doc_text = json.dumps(
        {
            "tools": [
                {"type": "function", "function": {"name": "get_weather", "description": "Weather by city"}},
                {"name": "send_mail", "description": "Send an email"},
            ],
            "variables": {"city": "The city name"},
            "examples": ["Input: Paris\nOutput: sunny"],
            "system": "Use get_weather for {{city}}.",
        },
        indent=2,
    )
    doc = analyze({"p.json": doc_text})
    check_spans(doc, {"p.json": doc_text})
    tools = {
        n.metadata["tool_description"] if "tool_description" in n.metadata else n.label: n
        for n in doc.nodes
        if n.type == "ToolNode"
    }
    assert {n.label for n in doc.nodes if n.type == "ToolNode"} == {"get_weather", "send_mail"}
    assert any(n.type == "ExampleNode" for n in doc.nodes)
    var = next(n for n in doc.nodes if n.type == "ContextNode")
    assert var.metadata["declared"] is True and var.label == "city"
    assert any(e.relation == "CALLS_TOOL" and e.status == "EXTRACTED" for e in doc.edges)
    assert tools


def test_txt_that_is_valid_json_is_read_as_json_but_prose_with_brackets_is_not():
    assert detect_format("p.txt", '{"a": "b"}') == "json"
    assert detect_format("p.txt", "[ref] Never lie.") == "text"
    assert detect_format("p.txt", '{"a": "b",}') == "text"  # not strictly valid: do not guess
    assert detect_format("P.JSON", "x") == "json" and detect_format("a.yml", "x") == "yaml"


def test_invalid_json_falls_back_to_plain_text_analysis():
    text = '{"system": "Never lie.", '
    doc = analyze({"p.json": text})
    check_spans(doc, {"p.json": text})
    assert any(n.original_text == "Never lie." for n in doc.nodes) or doc.nodes == []


# -------------------------------------------------------------------------------------------- YAML scalars
def test_yaml_align_literal_folded_quoted_plain():
    for src, style in (
        ("|\n  line one\n  line two\n", "|"),
        (">\n  folded one\n  continues here\n", ">"),
        ('"quoted \\"x\\" \\u00e9"', '"'),
        ("'it''s fine'", "'"),
        ("plain text here", ""),
    ):
        roots, notes = scan_yaml("k: " + src)
        assert notes == []
        node = roots[0].items[0][1]
        assert node.map_start is not None, f"alignment failed for {style!r}"
        raw = "k: " + src
        rebuilt = "".join(raw[a:b] for a, b in zip(node.map_start, node.map_end, strict=True))
        assert len(rebuilt) >= len(node.value)  # each decoded character has a non-empty raw origin


def test_yaml_align_fails_cleanly_on_mismatch():
    assert align("abc", "abd", "", 0) is None


def test_yaml_prompt_block_scalars_crlf_and_roles():
    text = "system: |\r\n  You are a bot.\r\n  Never lie.\r\ntask: >\r\n  Summarize the report\r\n  carefully.\r\n"
    doc = analyze({"p.yaml": text})
    check_spans(doc, {"p.yaml": text})
    by = {n.type: n for n in doc.nodes}
    assert by["SystemNode"].role_scope.role == "system"
    task = by["TaskNode"]
    assert task.original_text == "Summarize the report\r\n  carefully."  # raw slice spans the folded line break
    assert task.decoded_text == "Summarize the report carefully."


def test_yaml_tools_variables_examples_and_groups():
    text = (
        "variables:\n  doc: The document\n"
        "tools:\n  - name: search_web\n    description: Search the web\n"
        "examples:\n  - 'Input: a\\nOutput: b'\n"
        "constraints:\n  tone: formal\n  limit: 50 words\n"
        "task: Search for {{doc}} with search_web.\n"
    )
    doc = analyze({"p.yaml": text})
    check_spans(doc, {"p.yaml": text})
    kinds = [n.type for n in doc.nodes]
    assert kinds.count("ToolNode") == 1 and kinds.count("ExampleNode") == 1
    assert any(n.type == "ContextNode" and n.metadata["declared"] for n in doc.nodes)
    cons = [n.original_text for n in doc.nodes if n.type == "ConstraintNode"]
    assert "tone: formal" in cons and "limit: 50 words" in cons


def test_yaml_hostile_documents_are_contained():
    bomb = "a: &a [x, x, x, x, x, x, x, x, x]\n" + "".join(
        f"{c}: &{c} [*{p}, *{p}, *{p}, *{p}]\n" for p, c in zip("abcdefgh", "bcdefghi", strict=True)
    )
    for text in (
        bomb,
        "!!python/object/apply:os.system ['echo pwned']",
        "a: [1, 2\n",
        "\t- bad",
        "key: value: more: x",
        "---\n---\n---",
    ):
        doc = analyze({"p.yaml": text})  # never raises, never executes anything
        check_spans(doc, {"p.yaml": text})


def test_yaml_multi_document_and_front_matter_like_input():
    text = "system: You are a bot today.\n---\ntask: Summarize the report.\n"
    doc = analyze({"p.yaml": text})
    check_spans(doc, {"p.yaml": text})
    assert {n.type for n in doc.nodes} >= {"SystemNode", "TaskNode"}


def test_enclosing_fallback_is_flagged_not_guessed():
    # A decoded string whose map is missing must be reported as one unit with span_precision 'enclosing'.
    from promptgraphify import structured

    node = DNode("str", 8, 40, "Never share the password with anyone.", map_start=None, map_end=None, style='"')
    text = 'system: "Never share the password with anyone."\n'
    from promptgraphify.extract import SourceData

    data = SourceData("p.yaml", text, fmt="yaml")
    structured._Walker("p.yaml", text, data).enclosing(node, None)
    d = data.drafts[0]
    assert d.precision == "enclosing" and d.type == "ConstraintNode" and d.confidence <= 0.6
    assert d.span == (8, 40) and d.text == text[8:40]


# ---------------------------------------------------------------------------------------------- properties
JSONISH = st.recursive(
    st.one_of(st.none(), st.booleans(), st.integers(), st.text(max_size=40)),
    lambda inner: st.one_of(st.lists(inner, max_size=4), st.dictionaries(st.text(max_size=8), inner, max_size=4)),
    max_leaves=12,
)


@settings(max_examples=120, deadline=None)
@given(JSONISH, st.booleans())
def test_any_json_value_yields_valid_graphs_with_exact_spans(value, ensure_ascii):
    text = json.dumps({"system": value, "messages": [{"role": "user", "content": value}]}, ensure_ascii=ensure_ascii)
    doc = analyze({"p.json": text})
    check_spans(doc, {"p.json": text})


YAMLISH = st.lists(st.sampled_from(list("ab :-|>'\"\n\r\t#&*[]{}") + ["- ", "Never ", "{{x}}"]), max_size=40).map(
    "".join
)


@settings(max_examples=120, deadline=None)
@given(YAMLISH)
def test_arbitrary_yaml_like_text_never_crashes(text):
    doc = analyze({"p.yaml": text})
    check_spans(doc, {"p.yaml": text})
