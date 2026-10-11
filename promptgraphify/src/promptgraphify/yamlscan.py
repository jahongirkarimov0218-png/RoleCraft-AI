"""YAML front-end. Uses PyYAML's *composer* only (``yaml.compose_all`` with ``SafeLoader``): it builds a
node graph with exact character offsets and never constructs Python objects, so tags such as
``!!python/object`` cannot execute anything. Aliases are never followed twice and the node count is
capped, which stops entity-expansion ("billion laughs") documents.
"""

from __future__ import annotations

import yaml
from yaml.nodes import MappingNode, Node, ScalarNode, SequenceNode

from .docnode import DNode
from .markup import Note

MAX_NODES = 50_000
MAX_DEPTH = 100
STR_TAG = "tag:yaml.org,2002:str"
ESCAPES = {
    "0": "\0", "a": "\a", "b": "\b", "t": "\t", "\t": "\t", "n": "\n", "v": "\v", "f": "\f", "r": "\r", "e": "\x1b",
    " ": " ", '"': '"', "/": "/", "\\": "\\", "N": "\x85", "_": "\xa0", "L": " ", "P": " ",
}  # fmt: skip
HEX_ESCAPES = {"x": 2, "u": 4, "U": 8}


def _escape(raw: str, p: int) -> tuple[str, int]:
    """Decode the escape at ``raw[p] == '\\'``: (decoded, raw width). '' means a line continuation."""
    n = len(raw)
    e = raw[p + 1]
    if e in HEX_ESCAPES:
        w = HEX_ESCAPES[e]
        digits = raw[p + 2 : p + 2 + w]
        try:
            return chr(int(digits, 16)), 2 + w
        except ValueError:
            return e, 2
    if e in "\r\n":
        q = p + 2 if not (e == "\r" and p + 2 < n and raw[p + 2] == "\n") else p + 3
        while q < n and raw[q] in " \t":
            q += 1
        return "", q - p
    return ESCAPES.get(e, e), 2


def align(raw: str, decoded: str, style: str, base: int) -> tuple[list[int], list[int]] | None:
    """Raw offset (absolute, ``base`` + index) of every decoded character, or ``None`` if the scalar's
    text cannot be aligned with its decoded value (the caller then falls back to the enclosing span)."""
    n = len(raw)
    indent = 0
    p = 0
    if style in ("|", ">"):
        nl = raw.find("\n")
        if nl == -1:
            return ([], []) if not decoded else None
        p = nl + 1
        for line in raw[p:].splitlines():
            if line.strip():
                indent = len(line) - len(line.lstrip(" "))
                break
        p = _skip_indent(raw, p, style, indent)
    elif style in ("'", '"'):
        p = 1

    ms: list[int] = []
    me: list[int] = []
    for c in decoded:
        while True:
            if p >= n:
                return None
            r = raw[p]
            if style == '"' and r == "\\" and p + 1 < n:
                dec, w = _escape(raw, p)
                if dec == "":
                    p += w
                    continue
                if dec[0] != c:
                    return None
                ms.append(base + p)
                me.append(base + p + w)
                p += w
                break
            if style == "'" and r == "'" and raw[p + 1 : p + 2] == "'":
                if c != "'":
                    return None
                ms.append(base + p)
                me.append(base + p + 2)
                p += 2
                break
            if r in "\r\n":
                q = p + 2 if (r == "\r" and raw[p + 1 : p + 2] == "\n") else p + 1
                if c in "\n ":
                    ms.append(base + p)
                    me.append(base + q)
                    p = _skip_indent(raw, q, style, indent)
                    break
                p = _skip_indent(raw, q, style, indent)  # surplus blank line: not part of the decoded text
                continue
            if r == c:
                ms.append(base + p)
                me.append(base + p + 1)
                p += 1
                break
            if r in " \t" and c not in " \t":
                p += 1
                continue
            return None
    return ms, me


def _skip_indent(raw: str, p: int, style: str, indent: int) -> int:
    n = len(raw)
    if style == "|":
        k = 0
        while p < n and k < indent and raw[p] == " ":
            p += 1
            k += 1
        return p
    while p < n and raw[p] in " \t":
        p += 1
    return p


class _Converter:
    def __init__(self, text: str, offset: int = 0):
        self.text = text
        self.seen: set[int] = set()
        self.count = 0
        self.notes: list[Note] = []

    def convert(self, node: Node, depth: int = 0) -> DNode | None:
        if id(node) in self.seen:
            return None  # an alias to a node already visited: never expand twice
        self.seen.add(id(node))
        self.count += 1
        if self.count > MAX_NODES or depth > MAX_DEPTH:
            if self.count == MAX_NODES + 1 or depth == MAX_DEPTH + 1:
                self.notes.append(
                    Note(
                        "invalid_yaml",
                        (node.start_mark.index, node.start_mark.index + 1),
                        "document is too large or too deep; the rest is ignored",
                    )
                )
            return None
        a, b = node.start_mark.index, node.end_mark.index
        if isinstance(node, ScalarNode):
            style = node.style or ""
            raw = self.text[a:b]
            is_str = node.tag == STR_TAG
            if not is_str:
                return DNode("scalar", a, b, node.value, style=style)
            value = node.value
            if style in ("|", ">"):
                value = value.rstrip("\n")
            mapping = align(raw, value, style, a)
            ms, me = mapping if mapping else (None, None)
            return DNode("str", a, b, value, map_start=ms, map_end=me, style=style)
        if isinstance(node, MappingNode):
            out = DNode("map", a, b)
            for k, v in node.value:
                key = self.convert(k, depth + 1) if isinstance(k, ScalarNode) else None
                val = self.convert(v, depth + 1)
                if key is not None and val is not None:
                    out.items.append((key, val))
            return out
        if isinstance(node, SequenceNode):
            out = DNode("seq", a, b)
            for v in node.value:
                val = self.convert(v, depth + 1)
                if val is not None:
                    out.items.append((None, val))
            return out
        return None


def scan_yaml(text: str) -> tuple[list[DNode], list[Note]]:
    """Root nodes of every document in ``text`` (usually one) plus notes about problems."""
    conv = _Converter(text)
    roots: list[DNode] = []
    try:
        for doc in yaml.compose_all(text, Loader=yaml.SafeLoader):
            if doc is not None:
                root = conv.convert(doc)
                if root is not None:
                    roots.append(root)
    except yaml.YAMLError as exc:
        mark = getattr(exc, "problem_mark", None)
        at = mark.index if mark is not None else 0
        conv.notes.append(
            Note("invalid_yaml", (at, at + 1), f"invalid YAML: {getattr(exc, 'problem', None) or type(exc).__name__}")
        )
    except (RecursionError, ValueError):
        conv.notes.append(Note("invalid_yaml", (0, 1), "YAML could not be read"))
    return roots, conv.notes
