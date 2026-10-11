"""Properties of the whole pipeline that must hold for *any* input: it never crashes, the result always
passes Layer C, the output is deterministic, IDs do not depend on offsets, spans are in code points."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from promptgraphify import graphjson
from promptgraphify.analyze import AnalysisError, analyze
from promptgraphify.ir import AnalysisConfig
from promptgraphify.validate import validate_document

from .fake_llm import FakeAdapter
from .fixture_loader import load_fixtures

FIXTURES = [f for f in load_fixtures() if f.name not in {"06_yaml_prompt", "07_json_messages"}]
ROOT = Path(__file__).parent.parent

MARKUP_ALPHABET = st.sampled_from(
    list("abcXYZ .,!?:;-*#`<>/\"'{}$()[]|\n\r\t")
    + ["{{", "}}", "</", "<x>", "</x>", "\U0001f600", "﻿", "Never ", "step 1", "1. ", "- ", "## "]
)


@settings(max_examples=250, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(st.lists(MARKUP_ALPHABET, max_size=60).map("".join))
def test_any_text_is_analysed_into_a_valid_graph(text):
    doc = analyze({"p.md": text})
    assert validate_document(doc) == []
    for n in doc.nodes:  # span invariant in code points, including emoji / CRLF / BOM
        assert text[n.source_span.start : n.source_span.end] == n.original_text
    for e in doc.edges:
        for ev in e.evidence:
            assert text[ev.span.start : ev.span.end] == ev.text
        if e.status == "EXTRACTED":
            assert e.reference and any(e.reference in ev.text for ev in e.evidence)


@settings(max_examples=60, deadline=None)
@given(st.text(max_size=400))
def test_arbitrary_unicode_never_crashes(text):
    assert validate_document(analyze({"p.txt": text})) == []


@pytest.mark.parametrize("fx", FIXTURES, ids=lambda f: f.name)
def test_every_fixture_yields_a_valid_graph_with_exact_spans(fx):
    doc = analyze(fx.files)
    assert validate_document(doc) == []
    for n in doc.nodes:
        assert fx.files[n.source_file][n.source_span.start : n.source_span.end] == n.original_text
        assert n.validation_status == "verified"


@pytest.mark.parametrize("fx", FIXTURES[:6], ids=lambda f: f.name)
def test_repeated_runs_are_byte_identical(fx):
    first = graphjson.dumps(analyze(fx.files))
    second = graphjson.dumps(analyze(dict(reversed(list(fx.files.items())))))  # input order must not matter
    assert first == second


def test_byte_identical_across_python_hash_seeds():
    code = (
        "import sys, json; from promptgraphify import graphjson; from promptgraphify.analyze import analyze;"
        "from pathlib import Path;"
        "files={p.name: p.read_bytes().decode('utf-8') for p in sorted(Path(sys.argv[1]).iterdir())"
        " if p.name!='expected.json'};"
        "sys.stdout.write(graphjson.dumps(analyze(files)))"
    )
    outputs = []
    for seed in ("0", "1", "4242"):
        env = {**os.environ, "PYTHONHASHSEED": seed}
        out = subprocess.run(  # noqa: S603
            [sys.executable, "-I", "-c", code, str(ROOT / "tests" / "fixtures" / "03_multi_agent_handoff")],
            capture_output=True, text=True, env=env, check=True, cwd=str(ROOT),
        )  # fmt: skip
        outputs.append(out.stdout)
    assert outputs[0] == outputs[1] == outputs[2] and len(outputs[0]) > 1000


def test_graph_id_depends_on_input_and_config():
    a = analyze({"p.txt": "You are a bot.\nNever lie.\n"})
    assert a.graph_id == analyze({"p.txt": "You are a bot.\nNever lie.\n"}).graph_id
    assert a.graph_id != analyze({"p.txt": "You are a bot.\nNever cheat.\n"}).graph_id
    layer_b = analyze(
        {"p.txt": "You are a bot.\nNever lie.\n"},
        AnalysisConfig(layer_b=True),
        adapter=FakeAdapter({"nodes": [], "edges": []}),  # the layer now needs a provider; this one proposes nothing
    )
    assert a.graph_id != layer_b.graph_id


def test_inserting_a_line_does_not_change_other_ids():
    base = "# Rules\nYou are a bot.\nNever lie.\nSummarize the report.\n"
    longer = "# Rules\nYou are a bot.\nKeep answers under 100 words.\nNever lie.\nSummarize the report.\n"
    ids_before = {n.original_text: n.id for n in analyze({"p.md": base}).nodes}
    ids_after = {n.original_text: n.id for n in analyze({"p.md": longer}).nodes}
    for text, nid in ids_before.items():
        assert ids_after[text] == nid, f"id of {text!r} moved"
    assert len(ids_after) == len(ids_before) + 1


def test_offsets_are_code_points_not_utf16_units():
    smile = "\U0001f600"
    text = f"{smile}{smile}\nNever lie.\n"
    doc = analyze({"p.txt": text})
    node = next(n for n in doc.nodes if n.type == "ConstraintNode")
    assert node.source_span.start == 3  # two emoji + one newline, 1 code point each
    assert len(text.encode("utf-16-le")) // 2 == len(text) + 2


def test_json_roundtrip_is_lossless():
    doc = analyze({"p.md": "# A\n1. Extract {{x}}.\n2. Check step 1.\nNever lie.\n"})
    again = graphjson.loads(graphjson.dumps(doc))
    assert again == doc


def test_wrong_schema_version_is_a_clear_error():
    data = json.loads(graphjson.dumps(analyze({"p.txt": "Never lie.\n"})))
    data["schema_version"] = "0.1"
    with pytest.raises(graphjson.UnsupportedGraph, match="schema_version"):
        graphjson.loads(json.dumps(data))
    with pytest.raises(graphjson.UnsupportedGraph):
        graphjson.loads("not json")


def test_atomic_write(tmp_path):
    target = tmp_path / "sub" / "graph.json"
    graphjson.write_atomic(target, "one\n")
    graphjson.write_atomic(target, "two\n")
    assert target.read_text() == "two\n"
    assert [p.name for p in target.parent.iterdir()] == ["graph.json"]  # no stray temp files


def test_limits_and_degenerate_inputs():
    with pytest.raises(AnalysisError):
        analyze({})
    with pytest.raises(AnalysisError, match="exceeds"):
        analyze({"p.txt": "x" * 20}, max_input_chars=10)
    for text in ("", "   \n\t", "\n" * 50, "﻿", "\r\n\r\n"):
        doc = analyze({"p.txt": text})
        assert doc.nodes == [] and validate_document(doc) == []


def test_pathological_shapes_do_not_hang_or_crash():
    one_long_line = "Never lie, " * 20_000 + "end."
    many_open_tags = "<a>" * 5_000 + "Never lie."
    deep_lists = "\n".join(" " * (2 * i) + "- Check item." for i in range(300))
    braces = "{{ " * 3_000
    for text in (one_long_line, many_open_tags, deep_lists, braces):
        assert validate_document(analyze({"p.md": text})) == []


# ------------------------------------------------------------------ the scale fix: lines_between
def _reference_lines(text, a, b):
    from promptgraphify.text import split_lines

    return [ln for ln in split_lines(text) if ln[1] > a and ln[0] < b]


@settings(max_examples=400, deadline=None)
@given(
    st.lists(st.sampled_from(["a", "B", ".", "!", " ", "1", ":", "\n", "\r", "\r\n", "é", "😀"]), max_size=60).map(
        "".join
    ),
    st.data(),
)
def test_lines_between_equals_filtering_the_full_split(text, data):
    from promptgraphify.text import lines_between

    a = data.draw(st.integers(0, len(text)))
    b = data.draw(st.integers(a, len(text)))
    assert lines_between(text, a, b) == _reference_lines(text, a, b)


# -------------------------------------------------------- the scale fix: conflict search only compares opposites
def _reference_conflicts(units, emit):
    """The original all-pairs search, kept as the oracle for the faster one."""
    from promptgraphify.relations import _signature

    cands = [u for u in units if u.type in ("ConstraintNode", "TaskNode")]
    sigs = {id(u): _signature(u.text) for u in cands}
    for i, a in enumerate(cands):
        for b in cands[i + 1 :]:
            if a.file != b.file or a.agent != b.agent:
                continue
            pa, ta = sigs[id(a)]
            pb, tb = sigs[id(b)]
            if pa is None or pb is None or pa == pb or len(ta) < 2 or len(tb) < 2:
                continue
            jac = len(ta & tb) / len(ta | tb)
            if jac == 1.0:
                emit(a, b, "CONFLICTS_WITH", "INFERRED", rule="conflict.polarity")
            elif jac >= 0.6:
                emit(a, b, "CONFLICTS_WITH", "AMBIGUOUS", rule="conflict.partial_overlap", meta=round(jac, 2))


CONFLICT_POOL = [
    "Always answer in formal English.",
    "Never answer in formal English.",
    "Always cite the source document.",
    "Never cite the source document.",
    "Always use a polite tone with the customer.",
    "Never use a polite tone with the customer.",
    "Keep every answer under 50 words.",
    "Never reveal the secret key.",
    "Always reveal the secret key.",
    "Summarize the report.",
    "Do not summarize the report.",
    "Always be brief.",
    "Never be brief.",
]


@settings(max_examples=200, deadline=None)
@given(st.lists(st.sampled_from(CONFLICT_POOL), min_size=2, max_size=30))
def test_the_faster_conflict_search_finds_exactly_what_the_all_pairs_search_found(sentences):
    from promptgraphify.extract import extract_source
    from promptgraphify.relations import _link_conflicts

    units = extract_source("p.txt", "\n".join(sentences)).drafts

    def run(fn):
        found = []
        fn(units, lambda a, b, rel, status, *rest, **kw: found.append((a.span, b.span, rel, status, kw.get("rule"))))
        return found

    assert run(_link_conflicts) == run(_reference_conflicts)


@settings(max_examples=500, deadline=None)
@given(
    st.lists(st.sampled_from(["a", "Z", "é", "я", "7", "_", ".", "'", "-", " ", "!", "😀", " "]), max_size=40).map(
        "".join
    ),
    st.data(),
)
def test_token_before_equals_the_regex_it_replaced(text, data):
    from promptgraphify.text import _TOKEN_BEFORE, token_before

    i = data.draw(st.integers(0, len(text)))
    line_start = data.draw(st.integers(0, i))
    m = _TOKEN_BEFORE.search(text, line_start, i)
    assert token_before(text, line_start, i) == (m.group(0) if m else "")
