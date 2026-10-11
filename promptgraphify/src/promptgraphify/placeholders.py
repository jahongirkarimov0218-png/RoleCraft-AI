"""Template placeholders: ``{{ name }}``, ``${name}`` and ``{name}`` (ANALYSIS_SPEC §4).

Only innermost well-formed placeholders are extracted. Nested (``{{ {{x}} }}``) and unbalanced
(``{{x``) openers never produce a variable; they are reported as ``Malformed`` so the analyzer can
raise ``template.malformed``."""

from __future__ import annotations

import re
from dataclasses import dataclass

from .text import Interval

WELL_DOUBLE = re.compile(r"\{\{\s*([^{}]*?)\s*\}\}")
WELL_DOLLAR = re.compile(r"\$\{\s*([^{}]*?)\s*\}")
WELL_SINGLE = re.compile(r"(?<![{$\w])\{([^\W\d][\w.\-]*)\}(?!\})")
OPENER = re.compile(r"\{\{")
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


def find_placeholders(text: str, a: int, b: int) -> tuple[list[Placeholder], list[Malformed]]:
    region = text[a:b]
    found: list[Placeholder] = []
    empty: list[Malformed] = []
    taken: list[Interval] = []
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

    bad: list[Malformed] = list(empty)
    closers = [a + m.start() for m in re.finditer(r"\}\}", region)]
    for m in OPENER.finditer(region):
        s = a + m.start()
        if any(t0 <= s < t1 for t0, t1 in taken):
            continue
        line_end = region.find("\n", m.start())
        line_end = b if line_end == -1 else a + line_end
        close = next(
            (c for c in closers if s + 1 < c < line_end and not any(t0 <= c < t1 for t0, t1 in taken)),
            None,
        )
        if close is not None:
            bad.append(Malformed((s, close + 2), "nested"))
        else:
            tail = re.match(r"\{\{\S*", region[m.start() :])
            bad.append(Malformed((s, s + (tail.end() if tail else 2)), "unbalanced"))
    bad.sort(key=lambda x: x.span)
    return found, bad
