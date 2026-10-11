"""Scale guards. Bounds are deliberately loose (about 10x what was measured on a 4-CPU sandbox, see
docs/PERFORMANCE.md): they exist to catch an accidental O(n^2) coming back, not to certify a speed.
Deselect them with ``-m 'not slow'``."""

import time

import pytest

from promptgraphify.analyze import analyze
from promptgraphify.exporters import to_html, to_report, to_svg
from promptgraphify.validate import validate_document

from .synthetic import synthetic_prompt

pytestmark = pytest.mark.slow


def best(fn, repeat=3):
    out = []
    for _ in range(repeat):
        t = time.perf_counter()
        result = fn()
        out.append(time.perf_counter() - t)
    return min(out), result


def test_a_150_unit_prompt_analyses_in_well_under_a_few_seconds_and_has_over_150_nodes():
    text = synthetic_prompt(150)
    seconds, doc = best(lambda: analyze({"p.md": text}))
    assert len(doc.nodes) >= 150 and validate_document(doc) == []
    assert seconds < 3.0, f"{seconds:.2f}s for {len(doc.nodes)} nodes"


def test_analysis_time_grows_roughly_linearly_not_quadratically():
    small_text, large_text = synthetic_prompt(300), synthetic_prompt(1200)  # 4x the input
    small, _ = best(lambda: analyze({"p.md": small_text}))
    large, doc = best(lambda: analyze({"p.md": large_text}))
    assert len(doc.nodes) > 1200
    assert large < small * 10, (
        f"4x input took {large / small:.1f}x (linear 4x, quadratic 16x): {small:.2f}s -> {large:.2f}s"
    )


def test_exports_of_a_large_graph_stay_fast_and_valid():
    doc = analyze({"p.md": synthetic_prompt(600)})
    for name, fn in (("html", to_html), ("report", to_report), ("svg", to_svg)):
        seconds, out = best(lambda fn=fn: fn(doc), 2)
        assert seconds < 5.0 and len(out) > 1000, f"{name}: {seconds:.2f}s"


def test_a_single_very_long_line_is_linear_not_quadratic():
    # one 120k-character line of sentences: the sentence splitter must not rescan the whole file per sentence
    text = " ".join(f"Check item {i} against the order." for i in range(3000))
    seconds, doc = best(lambda: analyze({"p.md": text}), 1)
    assert len(doc.nodes) >= 3000 and seconds < 20.0, f"{seconds:.2f}s"
