"""Low-level text helpers: line splitting and sentence splitting, always in absolute offsets of the raw
source (code points, nothing normalised)."""

from __future__ import annotations

import re

from .signals import SIGNALS, fold

Interval = tuple[int, int]

TERMINALS = (
    ".!?" + "\N{HORIZONTAL ELLIPSIS}\N{IDEOGRAPHIC FULL STOP}\N{FULLWIDTH EXCLAMATION MARK}\N{FULLWIDTH QUESTION MARK}"
)
CLOSERS = (
    "\"')]}*_"
    + "\N{RIGHT-POINTING DOUBLE ANGLE QUOTATION MARK}\N{RIGHT DOUBLE QUOTATION MARK}\N{RIGHT SINGLE QUOTATION MARK}"
)
_TOKEN_BEFORE = re.compile(r"[\w.'\-]+$")
WORD = re.compile(r"[\w'\-]+", re.UNICODE)


def split_lines(text: str) -> list[Interval]:
    """(start, end) of every line, end excluding the terminator (``\\n``, ``\\r\\n`` or ``\\r``)."""
    out: list[Interval] = []
    n, start, i = len(text), 0, 0
    while i < n:
        ch = text[i]
        if ch == "\n" or ch == "\r":
            out.append((start, i))
            i += 2 if ch == "\r" and i + 1 < n and text[i + 1] == "\n" else 1
            start = i
        else:
            i += 1
    if start < n or not out:
        out.append((start, n))
    return out


def trim(text: str, a: int, b: int) -> Interval | None:
    while a < b and text[a].isspace():
        a += 1
    while b > a and text[b - 1].isspace():
        b -= 1
    return (a, b) if b > a else None


def _is_boundary(text: str, line_start: int, i: int, j: int, line_end: int) -> bool:
    """Is the terminal character at ``i`` (closers end at ``j``) a sentence end?"""
    ch = text[i]
    if ch in TERMINALS and ch != ".":
        return True
    if j >= line_end:  # period at the end of the line
        return True
    # period followed by whitespace: guard abbreviations, initials, lowercase continuation
    m = _TOKEN_BEFORE.search(text, line_start, i)
    token = fold(m.group(0)).lower().strip(".'") if m else ""
    if token in SIGNALS.abbreviations:
        return False
    if len(token) == 1 and token.isalpha() and (i - 2 < line_start or text[i - 2].isspace()) and text[i - 1].isupper():
        return False
    k = j
    while k < line_end and text[k].isspace():
        k += 1
    return not (k < line_end and text[k].islower())


def split_sentences(text: str, a: int, b: int) -> list[Interval]:
    """Sentences of the region ``text[a:b]`` (may span several lines) as trimmed absolute intervals.

    A newline ends a sentence unless the sentence is unfinished (no terminal punctuation) and the next
    line starts with a lowercase letter (a hard-wrapped sentence)."""
    lines = [ln for ln in split_lines(text) if ln[1] > a and ln[0] < b]
    lines = [(max(s, a), min(e, b)) for s, e in lines]
    out: list[Interval] = []
    cur: int | None = None
    for idx, (s, e) in enumerate(lines):
        i = s
        while i < e:
            if cur is None:
                if text[i].isspace():
                    i += 1
                    continue
                cur = i
            if text[i] in TERMINALS:
                j = i + 1
                while j < e and text[j] in CLOSERS:
                    j += 1
                if _is_boundary(text, s, i, j, e):
                    out.append((cur, j))
                    cur = None
                    i = j
                    continue
                i = j
                continue
            i += 1
        if cur is not None:
            nxt = next(((ns, ne) for ns, ne in lines[idx + 1 :] if text[ns:ne].strip()), None)
            tail = trim(text, cur, e)
            continues = (
                bool(nxt)
                and text[next(k for k in range(nxt[0], nxt[1]) if not text[k].isspace())].islower()
                and bool(tail)
            )
            if not continues and tail:
                out.append((tail[0], tail[1]))
                cur = None
    if cur is not None:
        tail = trim(text, cur, b)
        if tail:
            out.append(tail)
    return [iv for iv in (trim(text, x, y) for x, y in out) if iv]


def words(text: str) -> list[tuple[str, int, int]]:
    """Lower-cased, apostrophe-folded words with offsets relative to ``text``."""
    return [(fold(m.group(0)).lower(), m.start(), m.end()) for m in WORD.finditer(text)]
