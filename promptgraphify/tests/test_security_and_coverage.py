from hypothesis import given
from hypothesis import strategies as st

from promptgraphify.coverage import compute_coverage, merge_spans, subtract
from promptgraphify.security import MAX_LABEL_LEN, is_clean_label, sanitize_label
from promptgraphify.spans import Span


def test_sanitize_label_by_hand():
    assert sanitize_label("  Hello\n\tWorld  ") == "Hello World"
    assert sanitize_label("a\x00b\x1bc") == "a b c"
    assert sanitize_label("ok\u202etxt") == "ok txt"  # bidi override removed
    assert sanitize_label(None) == "" and sanitize_label("") == ""
    assert sanitize_label("<script>alert(1)</script>") == "<script>alert(1)</script>"  # data, not HTML
    long = sanitize_label("x" * 500)
    assert len(long) == MAX_LABEL_LEN and long.endswith("…")


@given(st.text())
def test_sanitize_is_idempotent_and_safe(s):
    once = sanitize_label(s)
    assert sanitize_label(once) == once
    assert len(once) <= MAX_LABEL_LEN
    assert "\n" not in once and "\x00" not in once
    assert once == "" or is_clean_label(once)


def test_merge_and_subtract():
    spans = [Span(start=0, end=3), Span(start=2, end=5), Span(start=7, end=9), Span(start=9, end=9)]
    assert merge_spans(spans) == [(0, 5), (7, 9)]
    assert subtract([(0, 10)], [(2, 4), (6, 8)]) == [(0, 2), (4, 6), (8, 10)]
    assert subtract([(0, 3)], [(0, 3)]) == []
    assert subtract([(5, 8)], [(0, 3)]) == [(5, 8)]


def test_compute_coverage_by_hand():
    text = "# Title\nYou are X.\nSome loose prose here.\n"
    node = Span(start=text.index("You"), end=text.index("X.") + 2)
    heading = Span(start=0, end=7)
    cov = compute_coverage("p.md", text, [node], [heading])
    assert [text[s.start : s.end] for s in cov.uncovered_spans] == ["Some loose prose here."]
    nonspace = sum(1 for ch in text if not ch.isspace())
    assert cov.total == nonspace
    assert cov.covered == len("YouareX.")
    assert cov.structural == len("#Title")
    assert cov.covered + cov.structural + cov.uncovered == cov.total
    assert 0 < cov.ratio < 1


def test_node_wins_over_overlapping_structural_span():
    text = "abc def"
    cov = compute_coverage("p", text, [Span(start=0, end=3)], [Span(start=2, end=7)])
    assert cov.structural_spans == [Span(start=3, end=7)]
    assert cov.covered + cov.structural + cov.uncovered == cov.total


def test_empty_and_whitespace_only_text():
    for text in ("", "   \n\t "):
        cov = compute_coverage("p", text, [], [])
        assert (cov.total, cov.covered, cov.structural, cov.uncovered) == (0, 0, 0, 0)
        assert cov.ratio == 1.0


@given(
    st.text(alphabet="ab \n😀", max_size=60),
    st.lists(st.tuples(st.integers(0, 60), st.integers(0, 60)), max_size=5),
)
def test_partition_holds_for_arbitrary_spans(text, raw):
    clip = [(min(a, len(text)), min(b, len(text))) for a, b in raw]
    spans = [Span(start=min(a, b), end=max(a, b)) for a, b in clip]
    cov = compute_coverage("p", text, spans[: len(spans) // 2], spans[len(spans) // 2 :])
    assert cov.covered + cov.structural + cov.uncovered == cov.total
