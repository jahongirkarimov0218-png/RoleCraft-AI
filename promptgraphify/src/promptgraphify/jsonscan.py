"""Tolerant, offset-preserving JSON scanner.

``json.loads`` gives no offsets and rejects the small mistakes real prompt configs contain (trailing
commas, comments). This scanner never raises: it records a note for every problem, recovers, and keeps
exact raw offsets for every string, including a decoded-to-raw map for strings with escapes.
"""

from __future__ import annotations

from .docnode import DNode
from .markup import Note

MAX_DEPTH = 100
SIMPLE_ESCAPES = {'"': '"', "\\": "\\", "/": "/", "b": "\b", "f": "\f", "n": "\n", "r": "\r", "t": "\t"}
SCALAR_END = set(",]} \t\r\n")


class _Scanner:
    def __init__(self, text: str):
        self.t = text
        self.n = len(text)
        self.notes: list[Note] = []

    def note(self, a: int, b: int, message: str) -> None:
        self.notes.append(Note("invalid_json", (a, max(b, a + 1)), message))

    def ws(self, i: int) -> int:
        t, n = self.t, self.n
        while i < n:
            c = t[i]
            if c in " \t\r\n\N{ZERO WIDTH NO-BREAK SPACE}":
                i += 1
            elif t.startswith("//", i):
                j = t.find("\n", i)
                i = n if j == -1 else j + 1
            elif t.startswith("/*", i):
                j = t.find("*/", i + 2)
                i = n if j == -1 else j + 2
            else:
                break
        return i

    # ------------------------------------------------------------------ strings
    def string(self, i: int) -> tuple[DNode, int]:
        t, n = self.t, self.n
        start = i
        i += 1
        decoded: list[str] = []
        ms: list[int] = []
        me: list[int] = []
        closed = False
        while i < n:
            c = t[i]
            if c == '"':
                closed = True
                i += 1
                break
            if c == "\\" and i + 1 < n:
                e = t[i + 1]
                if e == "u" and i + 5 < n + 0 and _hex4(t, i + 2):
                    code = int(t[i + 2 : i + 6], 16)
                    width = 6
                    if 0xD800 <= code <= 0xDBFF and t.startswith("\\u", i + 6) and _hex4(t, i + 8):
                        low = int(t[i + 8 : i + 12], 16)
                        if 0xDC00 <= low <= 0xDFFF:
                            code = 0x10000 + ((code - 0xD800) << 10) + (low - 0xDC00)
                            width = 12
                    ch = chr(code) if not 0xD800 <= code <= 0xDFFF else "\N{REPLACEMENT CHARACTER}"
                    decoded.append(ch)
                    ms.append(i)
                    me.append(i + width)
                    i += width
                    continue
                if e in SIMPLE_ESCAPES:
                    decoded.append(SIMPLE_ESCAPES[e])
                    ms.append(i)
                    me.append(i + 2)
                    i += 2
                    continue
                self.note(i, i + 2, f"invalid escape \\{e}")
                decoded.append(e)
                ms.append(i)
                me.append(i + 2)
                i += 2
                continue
            if c in "\r\n":  # raw newline inside a string: JSON forbids it; recover at the line end
                self.note(start, i, "string is not closed before the end of the line")
                break
            decoded.append(c)
            ms.append(i)
            me.append(i + 1)
            i += 1
        if not closed and i >= n:
            self.note(start, n, "string is not closed")
        return DNode("str", start, i, "".join(decoded), map_start=ms, map_end=me, style='"'), i

    # ------------------------------------------------------------------ values
    def value(self, i: int, depth: int) -> tuple[DNode | None, int]:
        i = self.ws(i)
        if i >= self.n:
            return None, i
        c = self.t[i]
        if depth > MAX_DEPTH:
            self.note(i, i + 1, "nesting is too deep")
            return DNode("scalar", i, self.n, self.t[i : self.n]), self.n
        if c == '"':
            return self.string(i)
        if c == "{":
            return self.mapping(i, depth)
        if c == "[":
            return self.sequence(i, depth)
        j = i
        while j < self.n and self.t[j] not in SCALAR_END:
            j += 1
        if j == i:  # a stray delimiter
            self.note(i, i + 1, f"unexpected {c!r}")
            return None, i + 1
        return DNode("scalar", i, j, self.t[i:j]), j

    def mapping(self, i: int, depth: int) -> tuple[DNode, int]:
        node = DNode("map", i, i)
        i += 1
        comma: int | None = None
        while True:
            i = self.ws(i)
            if i >= self.n:
                self.note(node.start, self.n, "object is not closed")
                break
            c = self.t[i]
            if c == "}":
                if comma is not None:
                    self.note(comma, comma + 1, "trailing comma")
                i += 1
                break
            if c == ",":
                if comma is not None:
                    self.note(i, i + 1, "unexpected comma")
                comma = i
                i += 1
                continue
            comma = None
            key, i = self.string(i) if c == '"' else self._bare_key(i)
            i = self.ws(i)
            if i < self.n and self.t[i] == ":":
                i += 1
            else:
                self.note(key.start, key.end, "missing ':' after key")
            val, i = self.value(i, depth + 1)
            if val is not None:
                node.items.append((key, val))
        node.end = i
        return node, i

    def _bare_key(self, i: int) -> tuple[DNode, int]:
        j = i
        while j < self.n and self.t[j] not in ':,}\r\n"':
            j += 1
        self.note(i, j, "key is not quoted")
        raw = self.t[i:j].rstrip()
        return DNode(
            "str",
            i,
            i + len(raw),
            raw,
            map_start=list(range(i, i + len(raw))),
            map_end=list(range(i + 1, i + len(raw) + 1)),
            style="",
        ), j

    def sequence(self, i: int, depth: int) -> tuple[DNode, int]:
        node = DNode("seq", i, i)
        i += 1
        comma: int | None = None
        while True:
            i = self.ws(i)
            if i >= self.n:
                self.note(node.start, self.n, "array is not closed")
                break
            c = self.t[i]
            if c == "]":
                if comma is not None:
                    self.note(comma, comma + 1, "trailing comma")
                i += 1
                break
            if c == ",":
                if comma is not None:
                    self.note(i, i + 1, "unexpected comma")
                comma = i
                i += 1
                continue
            comma = None
            val, i = self.value(i, depth + 1)
            if val is not None:
                node.items.append((None, val))
        node.end = i
        return node, i


def _hex4(t: str, i: int) -> bool:
    chunk = t[i : i + 4]
    return len(chunk) == 4 and all(ch in "0123456789abcdefABCDEF" for ch in chunk)


def scan_json(text: str) -> tuple[DNode | None, list[Note]]:
    s = _Scanner(text)
    root, i = s.value(0, 0)
    i = s.ws(i)
    if root is not None and i < s.n:
        s.note(i, s.n, "unexpected content after the JSON value")
    return root, s.notes
