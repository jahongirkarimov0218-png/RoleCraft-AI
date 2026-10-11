"""find_placeholders was quadratic (every match scanned every earlier match; every opener sliced the rest of the file;
a malformed span could run to the end of the file and was copied into its diagnostic). The rewrite is checked against
the original on short inputs, and its limits are checked on hostile ones."""

import re
import time

from hypothesis import given, settings
from hypothesis import strategies as st

from promptgraphify.analyze import analyze
from promptgraphify.placeholders import MAX_MALFORMED_SPAN, find_placeholders

WELL_DOUBLE = re.compile(r"\{\{\s*([^{}]*?)\s*\}\}")
WELL_DOLLAR = re.compile(r"\$\{\s*([^{}]*?)\s*\}")
WELL_SINGLE = re.compile(r"(?<![{$\w])\{([^\W\d][\w.\-]*)\}(?!\})")
OPENER = re.compile(r"\{\{")


def reference(text, a, b):
    """The original quadratic implementation, kept as the oracle (spans uncapped)."""
    from promptgraphify.placeholders import Malformed, Placeholder, root_name

    region = text[a:b]
    found, empty, taken = [], [], []
    for rx in (WELL_DOUBLE, WELL_DOLLAR, WELL_SINGLE):
        for m in rx.finditer(region):
            s, e = a + m.start(), a + m.end()
            if any(s < t1 and t0 < e for t0, t1 in taken):
                continue
            root = root_name(m.group(1))
            taken.append((s, e))
            if root is None:
                empty.append(Malformed((s, e), "empty"))
                continue
            found.append(Placeholder((s, e), root, m.group(1)))
    found.sort(key=lambda p: p.span)
    bad = list(empty)
    closers = [a + m.start() for m in re.finditer(r"\}\}", region)]
    for m in OPENER.finditer(region):
        s = a + m.start()
        if any(t0 <= s < t1 for t0, t1 in taken):
            continue
        line_end = region.find("\n", m.start())
        line_end = b if line_end == -1 else a + line_end
        close = next((c for c in closers if s + 1 < c < line_end and not any(t0 <= c < t1 for t0, t1 in taken)), None)
        if close is not None:
            bad.append(Malformed((s, close + 2), "nested"))
        else:
            tail = re.match(r"\{\{\S*", region[m.start() :])
            bad.append(Malformed((s, s + (tail.end() if tail else 2)), "unbalanced"))
    bad.sort(key=lambda x: x.span)
    return found, bad


@settings(max_examples=600, deadline=None)
@given(
    st.lists(st.sampled_from(list("{}$xa1 \n-.|") + ["{{", "}}", "${", "{{x}}"]), max_size=40).map("".join), st.data()
)
def test_the_rewrite_finds_exactly_what_the_original_found_on_short_inputs(text, data):
    a = data.draw(st.integers(0, len(text)))
    b = data.draw(st.integers(a, len(text)))
    # short inputs: every malformed span is below the cap, so the two must agree exactly
    assert find_placeholders(text, a, b) == reference(text, a, b)


def test_malformed_spans_are_capped_and_never_swallow_the_rest_of_the_file():
    text = "{{" + "y" * 5000 + "\nSummarize it.\n"
    (_, bad) = find_placeholders(text, 0, len(text))
    assert [(s, e - s) for (s, e), _k in [(m.span, m.kind) for m in bad]] == [
        (0, 42)
    ]  # '{{' + at most 40 glued characters
    far = (
        "{{ " + "x " * 100 + "{ }}"
    )  # a stray brace blocks a well-formed match; the closer is on the line but beyond the cap
    (_, bad) = find_placeholders(far, 0, len(far))
    assert [m.kind for m in bad] == ["unbalanced"] and all(m.span[1] - m.span[0] <= MAX_MALFORMED_SPAN for m in bad)


def test_hostile_template_floods_finish_quickly_and_report_bounded_evidence():
    for text in ("{{" * 60_000, "Use {{x}} " * 15_000, "{{ " * 4_000 + "x" + " }}" * 4_000, "${a} {b} " * 15_000):
        started = time.monotonic()
        doc = analyze({"p.md": text}, max_input_chars=600_000)
        assert time.monotonic() - started < 15, f"{text[:12]!r}: {time.monotonic() - started:.1f}s"
        longest = max((len(e.text) for d in doc.diagnostics for e in d.evidence), default=0)
        assert longest <= 1_000, f"diagnostic evidence of {longest} characters"


def test_a_flood_of_findings_is_capped_per_rule_and_the_cut_is_reported():
    from promptgraphify.analyzer import MAX_PER_RULE

    doc = analyze({"p.md": "{{" * 5_000}, max_input_chars=600_000)
    malformed = [d for d in doc.diagnostics if d.rule_id == "template.malformed"]
    assert len(malformed) == MAX_PER_RULE
    assert any(f"{5_000 - MAX_PER_RULE} more template.malformed finding(s) are not listed" in w for w in doc.warnings)
    assert len({d.id for d in doc.diagnostics}) == len(doc.diagnostics)  # still unique, still valid


def test_ordinary_prompts_are_not_capped():
    from promptgraphify.analyzer import cap_per_rule

    doc = analyze({"p.md": "Use {{x}} and {{y}}.\n{{ {{z}} }}\nSummarize it.\n"})
    kept, warnings = cap_per_rule(doc.diagnostics)
    assert kept == doc.diagnostics and warnings == [] and doc.warnings == []
