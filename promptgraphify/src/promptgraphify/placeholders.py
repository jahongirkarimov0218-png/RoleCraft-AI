"""Template placeholders: ``{{ name }}``, ``${name}`` and ``{name}`` (ANALYSIS_SPEC §4).

Only innermost well-formed placeholders are extracted. Nested (``{{ {{x}} }}``) and unbalanced
(``{{x``) openers never produce a variable; they are reported as ``Malformed`` so the analyzer can
raise ``template.malformed``."""

from __future__ import annotations

import re
from bisect import bisect_right
from dataclasses import dataclass

from .text import Interval

WELL_DOUBLE = re.compile(r"\{\{\s*([^{}]*?)\s*\}\}")
WELL_DOLLAR = re.compile(r"\$\{\s*([^{}]*?)\s*\}")
WELL_SINGLE = re.compile(r"(?<![{$\w])\{([^\W\d][\w.\-]*)\}(?!\})")
OPENER = re.compile(r"\{\{")
OPEN_TOKEN = re.compile(r"\{\{\S{0,40}")  # the opener and the non-space run glued to it, capped
ROOT = re.compile(r"^([^\W\d][\w.\-]*)")


@dataclass(frozen=True)
class Placeholder:
    span: Interval
    root: str  # variable name used for the node: "user" for {{user.name}}
    expr: str  # text inside the braces, e.g. "plan | upper"


@dataclass(frozen=True)
class Malformed:
    span: Interval
    kind: str  # "nested" | "unbalanced" | "empty"


def root_name(expr: str) -> str | None:
    m = ROOT.match(expr.strip())
    return m.group(1).split(".")[0] if m else None


MAX_MALFORMED_SPAN = 120  # a malformed template is reported with at most this much text as its evidence


class _Taken:
    """Non-overlapping intervals kept sorted, so "does this overlap?" is a bisection, not a scan."""

    def __init__(self) -> None:
        self.starts: list[int] = []
        self.ends: list[int] = []

    def overlaps(self, s: int, e: int) -> bool:
        i = bisect_right(self.starts, s) - 1
        if i >= 0 and self.ends[i] > s:
            return True
        return i + 1 < len(self.starts) and self.starts[i + 1] < e

    def contains(self, pos: int) -> bool:
        i = bisect_right(self.starts, pos) - 1
        return i >= 0 and self.starts[i] <= pos < self.ends[i]

    def add(self, s: int, e: int) -> None:
        i = bisect_right(self.starts, s)
        self.starts.insert(i, s)
        self.ends.insert(i, e)


def find_placeholders(text: str, a: int, b: int) -> tuple[list[Placeholder], list[Malformed]]:
    """Well-formed placeholders and malformed openers of ``text[a:b]``. Linear-ish in the region (bisection for
    overlap and line-end lookups), and a malformed span is capped at ``MAX_MALFORMED_SPAN`` characters."""
    region = text[a:b]
    found: list[Placeholder] = []
    empty: list[Malformed] = []
    taken = _Taken()
    for rx in (WELL_DOUBLE, WELL_DOLLAR, WELL_SINGLE):
        for m in rx.finditer(region):
            s, e = a + m.start(), a + m.end()
            if taken.overlaps(s, e):
                continue
            root = root_name(m.group(1))
            taken.add(s, e)
            if root is None:
                empty.append(Malformed((s, e), "empty"))
                continue
            found.append(Placeholder((s, e), root, m.group(1)))
    found.sort(key=lambda p: p.span)

    bad: list[Malformed] = list(empty)
    closers = [a + m.start() for m in re.finditer(r"\}\}", region)]
    newlines = [a + m.start() for m in re.finditer(r"\n", region)]
    for m in OPENER.finditer(region):
        s = a + m.start()
        if taken.contains(s):
            continue
        k = bisect_right(newlines, s)  # first newline after the opener
        line_end = newlines[k] if k < len(newlines) else b
        close = None
        j = bisect_right(closers, s + 1)  # first closer after s + 1
        while j < len(closers) and closers[j] < line_end:
            if not taken.contains(closers[j]):
                close = closers[j]
                break
            j += 1
        if close is not None and close + 2 - s <= MAX_MALFORMED_SPAN:
            bad.append(Malformed((s, close + 2), "nested"))
        else:
            tail = OPEN_TOKEN.match(region, m.start())
            bad.append(Malformed((s, s + (tail.end() - tail.start() if tail else 2)), "unbalanced"))
    bad.sort(key=lambda x: x.span)
    return found, bad
