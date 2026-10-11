"""Tolerant, offset-preserving scanner for plain text, Markdown and XML-flavoured prompts.

It never raises on bad input and never rewrites text: every output is a pair of absolute offsets into
the raw source. Real prompts mix Markdown and XML and leave tags unclosed, so instead of a strict
parser this module keeps a stack of *containers* (headings, tags, labels) and recovers when they are
not closed, recording each recovery as a ``Note`` (the analyzer turns notes into ``parse.malformed``).

Output (``Parsed``): ``blocks`` (prose paragraphs, list items, opaque blocks such as examples/context/
tool definitions), ``structural`` spans (recognised syntax that is not content) and ``notes``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .signals import SIGNALS, fold
from .text import Interval, split_lines, trim

BOM = "\N{ZERO WIDTH NO-BREAK SPACE}"
BULLETS = "-*+\N{BULLET}"

HEADING = re.compile(r"^( {0,3})(#{1,6})[ \t]+(.*?)[ \t]*#*[ \t]*$")
HRULE = re.compile(r"^ {0,3}(?:(?:-[ \t]*){3,}|(?:\*[ \t]*){3,}|(?:_[ \t]*){3,}|={3,})[ \t]*$")
LIST = re.compile(rf"^([ \t]*)(?:([{re.escape(BULLETS)}])|(\d{{1,3}})[.)])[ \t]+(\S.*)$")
FENCE = re.compile(r"^[ \t]{0,3}(`{3,}|~{3,})[ \t]*([\w+.\-]*)[ \t]*$")
TAG = re.compile(r"<(/?)([A-Za-z_][\w:.\-]*)((?:\s+[\w:.\-]+(?:\s*=\s*(?:\"[^\"]*\"|'[^']*'|[^\s\"'<>/]+))?)*)\s*(/?)>")
ATTR = re.compile(r"([\w:.\-]+)\s*=\s*(\"[^\"]*\"|'[^']*'|[^\s\"'<>/]+)")
TRAILING_CLOSE = re.compile(r"</([A-Za-z_][\w:.\-]*)\s*>[ \t]*$")
TOOL_SIG = re.compile(r"^`?([A-Za-z_][\w.\-]*)`?\s*(?:\(([^)]*)\))?\s*(?::\s*(\S.*))?$")
# ``### tool_name`` under a tools heading: backticked, or shaped like an identifier (snake_case, camelCase, dotted)
TOOL_HEADING = re.compile(r"^(`)?([A-Za-z_][\w.\-]*)`?(?:\s*\([^)]*\))?$")
VAR_DECL = re.compile(r"^`?([^\W\d][\w.\-]*)`?\s*(?::|—|-)\s*(\S.*)$")


@dataclass(eq=False)
class Container:
    kind: str  # "heading" | "tag" | "label"
    name: str
    level: int  # heading level 1-6; tags and labels use 100
    span: Interval  # the opener (heading line, tag, label line)
    parent: Container | None
    flags: set[str] = field(default_factory=set)
    role: str | None = None
    agent: str | None = None
    attrs: dict[str, str] = field(default_factory=dict)
    collect: list[Interval] = field(default_factory=list)
    chunks: list[list[Interval]] = field(default_factory=list)
    split_on_blank: bool = False
    eol_close: bool = False  # recovered: closes at the end of its line
    explicit_close: bool = False

    def path(self) -> list[str]:
        chain, c = [], self
        while c is not None:
            chain.append(c.name)
            c = c.parent
        return chain[::-1]

    def chain(self) -> list[Container]:
        out, c = [], self
        while c is not None:
            out.append(c)
            c = c.parent
        return out[::-1]


@dataclass
class Block:
    kind: str  # "prose" | "item" | "opaque"
    span: Interval
    ctx: Container | None
    sub: str = ""  # opaque: example | context | tool_def | tool_sig | tool_json | var_decl | code
    marker: Interval | None = None
    ordinal: int | None = None
    list_id: int | None = None
    depth: int = 0
    lead_in: str | None = None
    name: str | None = None
    attrs: dict[str, str] = field(default_factory=dict)
    desc: str | None = None
    opener: Interval | None = None  # opening tag / label / heading span of a collecting container


@dataclass
class Note:
    kind: str  # unclosed_tag | unexpected_close | unclosed_fence
    span: Interval
    message: str


@dataclass
class Parsed:
    text: str
    blocks: list[Block] = field(default_factory=list)
    structural: list[Interval] = field(default_factory=list)
    notes: list[Note] = field(default_factory=list)
    containers: list[Container] = field(default_factory=list)


def role_of(c: Container | None) -> str | None:
    while c is not None:
        if c.role:
            return c.role
        c = c.parent
    return None


def agent_of(c: Container | None) -> str | None:
    while c is not None:
        if c.agent:
            return c.agent
        c = c.parent
    return None


def _flags_for(name: str, kind: str) -> set[str]:
    low = fold(name.strip()).lower()
    flags: set[str] = set()
    if low in SIGNALS.example_names:
        flags.add("example")
    if low in SIGNALS.context_names:
        flags.add("context")
    if low in SIGNALS.tool_names:
        flags.add("tools")
    if kind == "tag" and low in SIGNALS.tool_def_names:
        flags.add("tool_def")
    if low in SIGNALS.variable_names:
        flags.add("variables")
    if low in SIGNALS.constraint_groups:
        flags.add("group")
    return flags


class _Scanner:
    def __init__(self, text: str, base: Container | None = None):
        self.text = text
        self.out = Parsed(text)
        self.base = base  # enclosing container supplied by a YAML/JSON front-end; never popped
        self.stack: list[Container] = [base] if base is not None else []
        self.baseline = len(self.stack)
        self.para: list[int] | None = None  # [start, end, ctx-index]
        self.para_ctx: Container | None = None
        self.item: dict | None = None
        self.lists: dict[int, tuple[int, str]] = {}
        self.next_list = 1
        self.lead_in: str | None = None
        self.fence: dict | None = None
        self.in_comment = False
        self.lines = split_lines(text)

    # ------------------------------------------------------------------ helpers
    @property
    def top(self) -> Container | None:
        return self.stack[-1] if self.stack else None

    def _struct(self, a: int, b: int) -> None:
        if b > a:
            self.out.structural.append((a, b))

    def _ancestor_flag(self, flag: str) -> bool:
        return any(flag in c.flags for c in self.stack)

    def _collector(self) -> Container | None:
        for c in reversed(self.stack):
            if c.flags & {"example", "context", "tool_def"}:
                return c
        return None

    # ------------------------------------------------------------------ containers
    def _push(self, c: Container) -> Container:
        self.stack.append(c)
        self.out.containers.append(c)
        return c

    def _flush(self, c: Container) -> None:
        chunks = [*c.chunks, c.collect]
        c.chunks, c.collect = [], []
        sub = "example" if "example" in c.flags else "context" if "context" in c.flags else "tool_def"
        if sub == "tool_def" and c.kind == "heading" and not any(chunks):
            # a tool heading with no body: the heading text itself is the definition
            raw = self.text[c.span[0] : c.span[1]]
            a = c.span[0] + len(raw) - len(raw.lstrip("#"))
            t = trim(self.text, a, c.span[1])
            if t is not None:
                self.out.blocks.append(
                    Block("opaque", t, c, sub=sub, name=c.attrs.get("name"), attrs=dict(c.attrs), opener=c.span)
                )
        for chunk in (ch for ch in chunks if ch):
            span = (chunk[0][0], chunk[-1][1])
            self.out.blocks.append(
                Block("opaque", span, c, sub=sub, name=c.attrs.get("name"), attrs=dict(c.attrs), opener=c.span)
            )

    def _pop(self) -> Container:
        c = self.stack.pop()
        if c.flags & {"example", "context", "tool_def"}:
            self._flush(c)
        return c

    def _pop_labels(self) -> None:
        while self.top is not None and self.top is not self.base and self.top.kind == "label":
            self._pop()

    # ------------------------------------------------------------------ paragraphs and items
    def _end_paragraph(self) -> None:
        if self.para is not None:
            a, b = self.para
            self.out.blocks.append(Block("prose", (a, b), self.para_ctx, lead_in=self.lead_in))
            self.para = None

    def _end_item(self) -> None:
        if self.item is not None:
            it = self.item
            self.out.blocks.append(
                Block(
                    "item",
                    (it["cs"], it["ce"]),
                    it["ctx"],
                    marker=it["marker"],
                    ordinal=it["ordinal"],
                    list_id=it["list_id"],
                    depth=it["depth"],
                    lead_in=it["lead_in"],
                )
            )
            self.item = None

    def _end_text(self) -> None:
        self._end_paragraph()
        self._end_item()

    # ------------------------------------------------------------------ line dispatch
    def run(self) -> Parsed:
        text = self.text
        for idx, (s, e) in enumerate(self.lines):
            if idx == 0 and text[s : s + 1] == BOM:
                self._struct(s, s + 1)
                s += 1
            if self.in_comment:
                self._struct(s, e)
                if "-->" in text[s:e]:
                    self.in_comment = False
                continue
            if self.fence is not None:
                self._fence_line(idx, s, e)
                continue
            raw = text[s:e]
            if not raw.strip():
                self._blank()
                continue
            self._line(idx, s, e, raw)
        self._finish()
        return self.out

    def _blank(self) -> None:
        self._end_text()
        coll = self._collector()
        if coll is not None and coll.split_on_blank and coll.collect:
            coll.chunks.append(coll.collect)
            coll.collect = []
        self._pop_labels()
        if not (self.top and self.top.kind == "label"):
            pass
        self.lead_in = None

    def _line(self, idx: int, s: int, e: int, raw: str) -> None:
        text = self.text
        stripped = raw.lstrip()
        ls = s + (len(raw) - len(stripped))
        if stripped.startswith("<!--"):
            self._end_text()
            self._struct(ls, e)
            self.in_comment = "-->" not in stripped
            return
        fence = FENCE.match(raw)
        if fence:
            self._open_fence(idx, s, e, fence)
            return
        if self._collector() is None:
            h = HEADING.match(raw)
            if h:
                self._heading(s, e, h)
                return
            if HRULE.match(raw):
                self._end_text()
                self._struct(ls, e)
                return
        else:
            h = HEADING.match(raw)
            if h:
                self._heading(s, e, h)
                return
        if stripped.startswith("<") and TAG.match(text, ls, e):
            self._tag_line(s, ls, e)
            return
        self._text_line(idx, s, e, raw)

    # ------------------------------------------------------------------ headings
    def _heading(self, s: int, e: int, m: re.Match) -> None:
        self._end_text()
        level = len(m.group(2))
        title = m.group(3).strip()
        while (
            self.top is not None
            and self.top is not self.base
            and self.top.kind not in ("tag", "key", "object")
            and (self.top.kind == "label" or self.top.level >= level)
        ):
            self._pop()
        low = fold(title).lower()
        agent_m = SIGNALS.match_common("agent_heading", title)
        c = Container("heading", title, level, (s + m.start(2), e), self.top)
        c.flags = _flags_for(title, "heading")
        c.role = SIGNALS.heading_roles.get(low)
        c.agent = agent_m.group("name").strip() if agent_m else None
        c.split_on_blank = bool(c.flags & {"example", "context"})
        if self._ancestor_flag("tools") and "tools" not in c.flags:
            tm = TOOL_HEADING.match(title)
            if tm and (
                tm.group(1) or "_" in tm.group(2) or "." in tm.group(2) or re.search(r"[a-z][A-Z]", tm.group(2))
            ):
                c.flags.add("tool_def")  # the section body is the tool's definition (D-023)
                c.attrs["name"] = tm.group(2)
        self._push(c)
        self._struct(s + m.start(2), e)
        self.lead_in = None
        self.lists.clear()

    # ------------------------------------------------------------------ tags
    @staticmethod
    def _attrs(raw: str) -> dict[str, str]:
        return {k: v.strip("\"'") for k, v in ATTR.findall(raw or "")}

    def _tag_line(self, s: int, ls: int, e: int) -> None:
        text = self.text
        self._end_text()
        tags: list[re.Match] = []
        pos = ls
        while True:
            m = TAG.match(text, pos, e)
            if not m:
                break
            tags.append(m)
            pos = m.end()
            k = pos
            while k < e and text[k] in " \t":
                k += 1
            if k < e and text[k] == "<" and TAG.match(text, k, e):
                pos = k
                continue
            break
        open_names = {fold(m.group(2)).lower() for m in tags if not m.group(1) and not m.group(4)}
        known = open_names | {fold(c.name).lower() for c in self.stack if c.kind == "tag"}
        trailing: list[re.Match] = []
        ce = e
        while True:
            mm = TRAILING_CLOSE.search(text, pos, ce)
            if not mm or fold(mm.group(1)).lower() not in known:
                break
            trailing.insert(0, mm)
            ce = mm.start()
        content = trim(text, pos, ce)
        opened_here: list[Container] = []
        for m in tags:
            name = m.group(2)
            if m.group(1):  # closing tag
                self._struct(m.start(), m.end())
                self._close_tag(name, (m.start(), m.end()))
            elif m.group(4):  # self-closing
                self._struct(m.start(), m.end())
            else:
                c = Container("tag", name, 100, (m.start(), m.end()), self.top)
                low = fold(name).lower()
                c.attrs = self._attrs(m.group(3))
                c.flags = _flags_for(name, "tag")
                c.role = SIGNALS.tag_roles.get(low)
                if low == "agent" and "name" in c.attrs:
                    c.agent = c.attrs["name"]
                c.split_on_blank = False
                self._push(c)
                self._struct(m.start(), m.end())
                opened_here.append(c)
        # recovery: content on the opening line but no closing tag anywhere -> the element ends at EOL
        closing_here = {fold(m.group(1)).lower() for m in trailing}
        for c in opened_here:
            low = fold(c.name).lower()
            if low in closing_here:
                continue
            later = re.search(rf"</\s*{re.escape(c.name)}\s*>", text[e:], flags=re.IGNORECASE)
            if content is not None and not later:
                c.eol_close = True
        if content is not None:
            self._text_line(-1, content[0], content[1], text[content[0] : content[1]], from_tag=True)
            self._end_text()
        for m in trailing:
            self._struct(m.start(), m.end())
            self._close_tag(m.group(1), (m.start(), m.end()))
        for c in opened_here:
            if c.eol_close and c in self.stack:
                self.out.notes.append(
                    Note(
                        "unclosed_tag",
                        c.span,
                        f"<{c.name}> is never closed; treated as ending at the end of its line",
                    )
                )
                while self.stack and self.stack[-1] is not c:
                    self._pop()
                self._pop()

    def _close_tag(self, name: str, span: Interval) -> None:
        low = fold(name).lower()
        self._end_text()
        for i in range(len(self.stack) - 1, -1, -1):
            c = self.stack[i]
            if c.kind == "tag" and fold(c.name).lower() == low:
                while len(self.stack) - 1 > i:
                    inner = self._pop()
                    if inner.kind == "tag":
                        self.out.notes.append(
                            Note("unclosed_tag", inner.span, f"<{inner.name}> is not closed before </{name}>")
                        )
                c = self._pop()
                c.explicit_close = True
                return
        self.out.notes.append(Note("unexpected_close", span, f"</{name}> has no matching opening tag"))

    # ------------------------------------------------------------------ fences
    def _open_fence(self, idx: int, s: int, e: int, m: re.Match) -> None:
        coll = self._collector()
        self._end_text()
        self.fence = {
            "char": m.group(1)[0],
            "len": len(m.group(1)),
            "lang": m.group(2),
            "body": [],
            "open": (s, e),
            "coll": coll,
        }
        if coll is not None:
            coll.collect.append(trim(self.text, s, e) or (s, e))
        else:
            self._struct(*(trim(self.text, s, e) or (s, e)))

    def _fence_line(self, idx: int, s: int, e: int) -> None:
        f = self.fence
        raw = self.text[s:e]
        m = FENCE.match(raw)
        closing = bool(m and m.group(1)[0] == f["char"] and len(m.group(1)) >= f["len"] and not m.group(2))
        if f["coll"] is not None:
            iv = trim(self.text, s, e)
            if iv:
                f["coll"].collect.append(iv)
        elif closing:
            body = f["body"]
            if body:
                span = (body[0][0], body[-1][1])
                tools = self._ancestor_flag("tools")
                self.out.blocks.append(
                    Block(
                        "opaque",
                        span,
                        self.top,
                        sub="tool_json" if tools else "code",
                        attrs={"lang": f["lang"]},
                    )
                )
            self._struct(*(trim(self.text, s, e) or (s, e)))
        else:
            iv = trim(self.text, s, e)
            if iv:
                f["body"].append(iv)
        if closing:
            self.fence = None

    # ------------------------------------------------------------------ text lines
    def _text_line(self, idx: int, s: int, e: int, raw: str, from_tag: bool = False) -> None:
        text = self.text
        coll = self._collector()
        if coll is not None:
            iv = trim(text, s, e)
            if iv:
                coll.collect.append(iv)
            return
        lm = LIST.match(raw)
        indent = len(raw) - len(raw.lstrip())
        if lm:
            self._end_text()
            ind = len(lm.group(1).replace("\t", "    "))
            depth = sum(1 for k in self.lists if k < ind)
            kind = "bullet" if lm.group(2) else "number"
            for k in [k for k in self.lists if k > ind]:
                del self.lists[k]
            if ind not in self.lists or self.lists[ind][1] != kind:
                self.lists[ind] = (self.next_list, kind)
                self.next_list += 1
            list_id = self.lists[ind][0]
            ms = s + len(lm.group(1))
            marker_end = ms + (len(lm.group(2)) if lm.group(2) else len(lm.group(3)) + 1)  # token only
            cs, ce = s + lm.start(4), e
            ce = trim(text, cs, ce)[1]
            if self._ancestor_flag("tools") and self._tool_sig(cs, ce, marker=(ms, marker_end)):
                return
            if self._ancestor_flag("variables") and self._var_decl(cs, ce, marker=(ms, marker_end)):
                return
            self._struct(ms, marker_end)
            self.item = {
                "cs": cs,
                "ce": ce,
                "ctx": self.top,
                "marker": (ms, marker_end),
                "ordinal": int(lm.group(3)) if lm.group(3) else None,
                "list_id": list_id,
                "depth": depth,
                "lead_in": self.lead_in,
                "indent": ind,
            }
            return
        trimmed = trim(text, s, e)
        if trimmed is None:
            return
        if self.item is not None and (indent > self.item["indent"] or (indent == 0 and raw[:1].islower())):
            self.item["ce"] = trimmed[1]
            return
        self._end_item()
        if self._ancestor_flag("tools") and self._tool_sig(trimmed[0], trimmed[1]):
            return
        if self._ancestor_flag("variables") and self._var_decl(trimmed[0], trimmed[1]):
            return
        stripped = raw.strip()
        if stripped.endswith(":") and self.para is None:
            kinds = (
                ("label_example", "example"),
                ("label_context", "context"),
                ("label_tools", "tools"),
                ("label_variables", "variables"),
            )
            for key, flag in kinds:
                m = SIGNALS.match_common(key, stripped)
                if m:
                    self._pop_labels()
                    c = Container("label", stripped.rstrip(":").strip(), 100, trimmed, self.top, flags={flag})
                    self._push(c)
                    self._struct(*trimmed)
                    return
            if self._next_is_list_or_indented(idx, e):
                self._struct(*trimmed)
                self.lead_in = stripped
                self.lists.clear()
                return
        if self.para is None:
            self.para = [trimmed[0], trimmed[1]]
            self.para_ctx = self.top
            self.lists.clear()
        else:
            self.para[1] = trimmed[1]

    def _next_is_list_or_indented(self, idx: int, e: int) -> bool:
        if idx < 0:
            return False
        for ns, ne in self.lines[idx + 1 :]:
            raw = self.text[ns:ne]
            if not raw.strip():
                return False
            return bool(LIST.match(raw)) or raw[:1] in " \t"
        return False

    # ------------------------------------------------------------------ tools and variables
    def _tool_sig(self, cs: int, ce: int, marker: Interval | None = None) -> bool:
        m = TOOL_SIG.match(self.text[cs:ce])
        if not m or (m.group(2) is None and m.group(3) is None and "_" not in m.group(1)):
            return False
        if marker:
            self._struct(*marker)
        self.out.blocks.append(Block("opaque", (cs, ce), self.top, sub="tool_sig", name=m.group(1), desc=m.group(3)))
        return True

    def _var_decl(self, cs: int, ce: int, marker: Interval | None = None) -> bool:
        m = VAR_DECL.match(self.text[cs:ce])
        if not m:
            return False
        if marker:
            self._struct(*marker)
        self.out.blocks.append(Block("opaque", (cs, ce), self.top, sub="var_decl", name=m.group(1), desc=m.group(2)))
        return True

    # ------------------------------------------------------------------ end of input
    def _finish(self) -> None:
        self._end_text()
        if self.fence is not None:
            f = self.fence
            self.out.notes.append(Note("unclosed_fence", f["open"], "code fence is never closed"))
            body = f["body"]
            if body and f["coll"] is None:
                self.out.blocks.append(
                    Block("opaque", (body[0][0], body[-1][1]), self.top, sub="code", attrs={"lang": f["lang"]})
                )
            self.fence = None
        while len(self.stack) > self.baseline:
            c = self._pop()
            if c.kind == "tag" and not c.explicit_close and not c.eol_close:
                self.out.notes.append(
                    Note(
                        "unclosed_tag",
                        c.span,
                        f"<{c.name}> is never closed; treated as ending at the end of the input",
                    )
                )


def parse_markup(text: str, base: Container | None = None) -> Parsed:
    """Scan ``text``; blocks found at top level get ``base`` (a container supplied by a structured
    front-end, e.g. the YAML key that holds this string) as their enclosing container."""
    return _Scanner(text, base).run()
