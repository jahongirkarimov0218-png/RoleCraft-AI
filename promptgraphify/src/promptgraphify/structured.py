"""YAML / JSON front-end: turns a document tree into node drafts with exact raw spans.

Prompts stored as YAML or JSON keep their text inside string values. Those strings are decoded, analysed
with the same prose rules as every other input, and every resulting span is translated back to the raw
file through the string's decoded-to-raw map, so ``source[start:end] == original_text`` still holds even
with escapes such as ``\\"`` or ``\\u00e9`` (the decoded view goes to ``decoded_text``).
"""

from __future__ import annotations

from .classify import classify, condition_clause, is_otherwise, loop_info
from .docnode import DNode
from .extract import Draft, SourceData, VarUse, _opaque_drafts, extract_segment
from .jsonscan import scan_json
from .markup import Block, Container, Note, _flags_for
from .placeholders import Malformed, find_placeholders
from .signals import SIGNALS, fold
from .text import Interval, trim
from .yamlscan import scan_yaml

ROLE_ALIASES = {
    "system": "system", "developer": "developer", "user": "user", "assistant": "assistant", "tool": "tool",
    "human": "user", "ai": "assistant", "model": "assistant",
}  # fmt: skip
OPAQUE_FLAGS = {"example", "context", "tool_def", "tools", "variables"}


def detect_format(path: str, text: str) -> str:
    ext = path.lower().rsplit(".", 1)[-1] if "." in path else ""
    if ext == "json":
        return "json"
    if ext in ("yaml", "yml"):
        return "yaml"
    if ext in ("md", "markdown"):
        return "markdown"
    if ext == "xml":
        return "xml"
    head = text.lstrip("\N{ZERO WIDTH NO-BREAK SPACE} \t\r\n")
    if head[:1] in ("{", "["):  # a .txt that is really JSON, but only if it is strictly valid
        root, notes = scan_json(text)
        if root is not None and root.kind in ("map", "seq") and not notes:
            return "json"
    return "text"


def extract_structured(path: str, text: str, fmt: str) -> SourceData | None:
    """Layer A for YAML/JSON. ``None`` means the text is not readable as a document at all."""
    if fmt == "json":
        root, notes = scan_json(text)
        roots = [root] if root is not None else []
    else:
        roots, notes = scan_yaml(text)
    if not roots:
        return None
    data = SourceData(path, text, fmt=fmt, notes=list(notes))
    walker = _Walker(path, text, data)
    for root in roots:
        walker.walk(root, None)
    data.structural.extend(_complement(walker.prose_ranges, len(text)))
    data.drafts.sort(key=lambda d: (d.span[0], -d.span[1]))
    return data


def _complement(ranges: list[Interval], n: int) -> list[Interval]:
    out, pos = [], 0
    for a, b in sorted(ranges):
        if a > pos:
            out.append((pos, a))
        pos = max(pos, b)
    if pos < n:
        out.append((pos, n))
    return out


def _get(node: DNode, key: str) -> DNode | None:
    if node.kind != "map":
        return None
    for k, v in node.items:
        if k is not None and fold(k.key_text()).lower() == key:
            return v
    return None


class _Walker:
    def __init__(self, path: str, text: str, data: SourceData):
        self.path, self.text, self.data = path, text, data
        self.prose_ranges: list[Interval] = []

    # ------------------------------------------------------------------ tree walk
    def walk(self, node: DNode, ctx: Container | None) -> None:
        if node.kind == "map":
            self.walk_map(node, ctx)
        elif node.kind == "seq":
            for _, item in node.items:
                if item.kind == "map":
                    obj = self._object(item, ctx)
                    self.walk_map(item, obj)
                else:
                    self.walk(item, ctx)
        elif node.kind == "str":
            self.string(node, ctx)

    def _object(self, node: DNode, ctx: Container | None) -> Container:
        role_node = _get(node, "role")
        role = (
            ROLE_ALIASES.get(fold((role_node.value or "").strip()).lower())
            if role_node and role_node.kind == "str"
            else None
        )
        return Container("object", role or "item", 100, (node.start, node.start + 1), ctx, role=role)

    def walk_map(self, node: DNode, ctx: Container | None) -> None:
        for key, val in node.items:
            name = key.key_text() if key else ""
            low = fold(name).lower()
            flags = _flags_for(name, "tag")
            if low == "role" and val.kind == "str" and ROLE_ALIASES.get(fold((val.value or "").strip()).lower()):
                continue
            if (
                ctx is not None
                and "group" in ctx.flags
                and val.kind in ("str", "scalar")
                and len((val.value or "").split()) <= 6
            ):
                self.entry_unit(key, val, ctx)
                continue
            if "variables" in flags:
                self.declarations(val, ctx)
            elif "tools" in flags:
                self.tools(val, ctx)
            elif "example" in flags:
                self.examples(val, ctx)
            elif "context" in flags and val.kind == "str":
                self.opaque("context", self._inner(val), ctx)
            else:
                child = Container(
                    "key", name, 100, (key.start, key.end), ctx, flags - OPAQUE_FLAGS, role=SIGNALS.tag_roles.get(low)
                )
                if ctx is not None and fold(ctx.name).lower() in ("agents",):
                    child.agent = name
                if val.kind == "str":
                    self.string(val, child)
                else:
                    self.walk(val, child)

    # ------------------------------------------------------------------ opaque blocks
    @staticmethod
    def _inner(node: DNode) -> Interval:
        if node.kind == "str" and node.map_start:
            return (node.map_start[0], node.map_end[-1])  # type: ignore[index]
        return (node.start, node.end)

    def opaque(
        self, sub: str, span: Interval, ctx: Container | None, name: str | None = None, desc: str | None = None
    ) -> None:
        t = trim(self.text, *span)
        if not t:
            return
        block = Block("opaque", t, ctx, sub=sub, name=name, desc=desc)
        self.data.drafts.extend(_opaque_drafts(self.path, self.text, block, self.data.uses))

    def declarations(self, val: DNode, ctx: Container | None) -> None:
        if val.kind == "map":
            for key, v in val.items:
                self.opaque("var_decl", (key.start, v.end), ctx, name=key.key_text(), desc=v.value)
        elif val.kind == "seq":
            for _, it in val.items:
                if it.kind in ("str", "scalar"):
                    self.opaque("var_decl", (it.start, it.end), ctx, name=it.key_text())
                elif it.kind == "map":
                    n = _get(it, "name")
                    if n is not None and n.value:
                        d = _get(it, "description")
                        self.opaque("var_decl", (it.start, it.end), ctx, name=n.key_text(), desc=d.value if d else None)

    def _tool_name(self, node: DNode) -> str | None:
        n = _get(node, "name")
        if n is None or not n.value:
            fn = _get(node, "function")
            n = _get(fn, "name") if fn is not None else None
        return n.key_text() if n is not None and n.value else None

    def tools(self, val: DNode, ctx: Container | None) -> None:
        if val.kind == "seq":
            for _, it in val.items:
                if it.kind == "map" and (name := self._tool_name(it)):
                    d = _get(it, "description")
                    self.opaque("tool_def", (it.start, it.end), ctx, name=name, desc=d.value if d else None)
        elif val.kind == "map":
            if self._tool_name(val):
                self.opaque("tool_def", (val.start, val.end), ctx, name=self._tool_name(val))
                return
            for key, v in val.items:
                if v.kind == "map":
                    self.opaque("tool_def", (key.start, v.end), ctx, name=key.key_text())

    def examples(self, val: DNode, ctx: Container | None) -> None:
        if val.kind == "seq":
            for _, it in val.items:
                self.opaque("example", self._inner(it) if it.kind == "str" else (it.start, it.end), ctx)
        elif val.kind == "str":
            self.opaque("example", self._inner(val), ctx)
        elif val.kind == "map":
            self.opaque("example", (val.start, val.end), ctx)

    # ------------------------------------------------------------------ strings
    def entry_unit(self, key: DNode, val: DNode, ctx: Container) -> None:
        """`format: json` under a constraint group: the whole entry is one unit."""
        decoded = f"{key.key_text()}: {val.value}"
        cls = classify(decoded)
        t = trim(self.text, key.start, val.end)
        if cls is None or t is None:
            return
        raw = self.text[t[0] : t[1]]
        d = Draft(
            file=self.path, type=cls.type, span=t, text=raw, ctx=ctx, rule=cls.rule, confidence=cls.confidence,
            description=cls.description, cls=cls, block_key=id(key), decoded=decoded if decoded != raw else None,
        )  # fmt: skip
        d.meta["signals"] = cls.signals
        d.meta["entry"] = key.key_text()
        self.data.drafts.append(d)

    def string(self, node: DNode, ctx: Container | None) -> None:
        if not node.is_prose or node.value is None:
            return
        if node.map_start is None or node.map_end is None or len(node.map_start) != len(node.value):
            self.enclosing(node, ctx)
            return
        seg = extract_segment(self.path, node.value, base=ctx)
        ms, me = node.map_start, node.map_end

        def raw(span: Interval) -> Interval:
            a, b = span
            if not ms:
                return (node.start, node.start)
            if b > a:
                return (ms[min(a, len(ms) - 1)], me[min(b, len(me)) - 1])
            at = ms[a] if a < len(ms) else me[-1]
            return (at, at)

        for d in seg.drafts:
            a, b = raw(d.span)
            rt = self.text[a:b]
            if rt != d.text:
                d.decoded = d.decoded or d.text
                d.text = rt
            d.span = (a, b)
            if "_condition_span" in d.meta:
                d.meta["_condition_span"] = raw(d.meta["_condition_span"])
            if d.meta.get("_opener"):
                d.meta["_opener"] = raw(d.meta["_opener"])
            if d.item_line:
                d.item_line = raw(d.item_line)
        for u in seg.uses:
            u.span = raw(u.span)
            u.text = self.text[u.span[0] : u.span[1]]
        self.data.drafts.extend(seg.drafts)
        self.data.uses.extend(seg.uses)
        self.data.malformed.extend(Malformed(raw(m.span), m.kind) for m in seg.malformed)
        self.data.notes.extend(Note(n.kind, raw(n.span), n.message) for n in seg.notes)
        self.data.structural.extend(raw(s) for s in seg.structural)
        # an escape that stands for whitespace (\n, \t, \u0020) is layout, not unclassified text
        for i, ch in enumerate(node.value):
            if ch.isspace() and self.text[ms[i] : me[i]].strip():
                self.data.structural.append((ms[i], me[i]))
        self.prose_ranges.append((ms[0], me[-1]) if ms else (node.start, node.end))

    def enclosing(self, node: DNode, ctx: Container | None) -> None:
        """The decoded text could not be aligned with the raw text: report the whole scalar as one unit
        with ``span_precision = "enclosing"`` instead of guessing exact offsets."""
        decoded = (node.value or "").strip()
        t = trim(self.text, node.start, node.end)
        self.prose_ranges.append((node.start, node.end))
        if not decoded or t is None:
            return
        cls = classify(decoded)
        found, bad = find_placeholders(decoded, 0, len(decoded))
        raw = self.text[t[0] : t[1]]
        for p in found:
            self.data.uses.append(VarUse(self.path, t, p.root, p.expr, decoded[p.span[0] : p.span[1]], ctx=ctx))
        self.data.malformed.extend(Malformed(t, m.kind) for m in bad)
        if cls is None:
            return
        d = Draft(
            file=self.path, type=cls.type, span=t, text=raw, ctx=ctx, rule=cls.rule,
            confidence=min(cls.confidence, 0.6), description=cls.description, cls=cls,
            block_key=id(node), decoded=decoded, precision="enclosing",
        )  # fmt: skip
        d.meta["signals"] = cls.signals
        cond = condition_clause(decoded)
        if cond:
            d.meta["condition"] = decoded[cond[0] : cond[1]]
        if is_otherwise(decoded):
            d.meta["otherwise"] = True
        if loop := loop_info(decoded):
            d.meta["loop"] = loop
        self.data.drafts.append(d)
