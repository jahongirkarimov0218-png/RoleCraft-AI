"""Coverage accounting: which part of the prompt became nodes, which part is recognised syntax and
which part the deterministic layer did not understand (ANALYSIS_SPEC §2).

Every non-whitespace code point of a source lands in exactly one of three classes:
covered (inside at least one node), structural (recognised syntax) or uncovered.
"""

from __future__ import annotations

from .ir import SourceCoverage
from .spans import Span

Interval = tuple[int, int]


def merge_spans(spans: list[Span]) -> list[Interval]:
    """Union of spans as sorted, non-touching, non-empty intervals."""
    merged: list[list[int]] = []
    for s in sorted(spans, key=lambda x: (x.start, x.end)):
        if s.end == s.start:
            continue
        if merged and s.start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], s.end)
        else:
            merged.append([s.start, s.end])
    return [(a, b) for a, b in merged]


def intervals_overlap(a: list[Interval], b: list[Interval]) -> bool:
    i = j = 0
    while i < len(a) and j < len(b):
        if a[i][0] < b[j][1] and b[j][0] < a[i][1]:
            return True
        if a[i][1] <= b[j][1]:
            i += 1
        else:
            j += 1
    return False


def subtract(a: list[Interval], b: list[Interval]) -> list[Interval]:
    """Parts of ``a`` not covered by ``b`` (both sorted and merged)."""
    out: list[Interval] = []
    j = 0
    for start, end in a:
        cur = start
        while j < len(b) and b[j][1] <= cur:
            j += 1
        k = j
        while k < len(b) and b[k][0] < end:
            if b[k][0] > cur:
                out.append((cur, b[k][0]))
            cur = max(cur, b[k][1])
            k += 1
        if cur < end:
            out.append((cur, end))
    return out


def nonspace_prefix(text: str) -> list[int]:
    """``prefix[i]`` = number of non-whitespace code points in ``text[:i]``."""
    prefix = [0] * (len(text) + 1)
    for i, ch in enumerate(text):
        prefix[i + 1] = prefix[i] + (0 if ch.isspace() else 1)
    return prefix


def count_nonspace(prefix: list[int], intervals: list[Interval]) -> int:
    last = len(prefix) - 1
    return sum(prefix[min(b, last)] - prefix[min(a, last)] for a, b in intervals)


def _trim(text: str, start: int, end: int) -> Interval | None:
    while start < end and text[start].isspace():
        start += 1
    while end > start and text[end - 1].isspace():
        end -= 1
    return (start, end) if end > start else None


def compute_coverage(
    path: str, text: str, node_spans: list[Span], structural_spans: list[Span]
) -> SourceCoverage:
    """Partition ``text``: structural spans overlapping a node are clipped away so a node always
    wins; everything left over (trimmed of surrounding whitespace) is reported as uncovered."""
    prefix = nonspace_prefix(text)
    covered = merge_spans(node_spans)
    structural = subtract(merge_spans(structural_spans), covered)
    occupied = merge_spans([Span(start=a, end=b) for a, b in covered + structural])
    gaps = subtract([(0, len(text))], occupied)
    uncovered = [t for g in gaps if (t := _trim(text, *g)) is not None]
    return SourceCoverage(
        source_file=path,
        total=prefix[-1],
        covered=count_nonspace(prefix, covered),
        structural=count_nonspace(prefix, structural),
        uncovered=count_nonspace(prefix, uncovered),
        structural_spans=[Span(start=a, end=b) for a, b in structural],
        uncovered_spans=[Span(start=a, end=b) for a, b in uncovered],
    )
