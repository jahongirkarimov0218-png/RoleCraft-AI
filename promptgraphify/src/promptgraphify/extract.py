"""Layer A, per source file: scanner blocks -> node *drafts* (before IDs and cross-file linking).

A ``Draft`` carries everything a ``Node`` needs plus the scanner context (container, list position)
that the relation rules use. Drafts refer to each other by object identity; ``analyze.py`` turns them
into IDs only at the very end, so no rule ever depends on an ID.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from .classify import Classification, classify, condition_clause, is_otherwise, loop_info
from .markup import Block, Container, Note, Parsed, agent_of, parse_markup, role_of
from .ontology import NodeType
from .placeholders import Malformed, find_placeholders
from .text import Interval, split_sentences, trim

MAX_JSON_TOOL_BYTES = 200_000


@dataclass(eq=False)
class Draft:
    file: str
    type: NodeType
    span: Interval
    text: str
    ctx: Container | None
    rule: str  # extraction rule name
    confidence: float
    description: str
    name: str | None = None  # variables and tools are identified by name
    meta: dict = field(default_factory=dict)
    block: Block | None = None
    item_line: Interval | None = None  # marker start .. content end of the list item (evidence)
    marker_text: str | None = None
    ordinal: int | None = None
    list_id: int | None = None
    block_key: int = 0  # id() of the originating block: units of one list item share it
    cls: Classification | None = None
    decoded: str | None = None
    precision: str = "exact"

    @property
    def role(self) -> str | None:
        return role_of(self.ctx)

    @property
    def agent(self) -> str | None:
        return agent_of(self.ctx)

    def section_path(self) -> list[str]:
        return self.ctx.path() if self.ctx else []


@dataclass(eq=False)
class VarUse:
    file: str
    span: Interval
    root: str
    expr: str
    text: str
    container: str | None = None  # <document>{{doc}}</document> -> "document"
    ctx: Container | None = None
    unit: Draft | None = None
    produced: bool = False


@dataclass
class SourceData:
    path: str
    text: str
    parsed: Parsed
    drafts: list[Draft] = field(default_factory=list)
    uses: list[VarUse] = field(default_factory=list)
    malformed: list[Malformed] = field(default_factory=list)
    notes: list[Note] = field(default_factory=list)


def _unit_drafts(path: str, text: str, block: Block) -> list[Draft]:
    out: list[Draft] = []
    a, b = block.span
    for s, e in split_sentences(text, a, b):
        sentence = text[s:e]
        cls = classify(sentence)
        if cls is None:
            continue
        d = Draft(
            file=path,
            type=cls.type,
            span=(s, e),
            text=sentence,
            ctx=block.ctx,
            rule=cls.rule,
            confidence=cls.confidence,
            description=cls.description,
            block=block,
            cls=cls,
            block_key=id(block),
        )
        d.meta["signals"] = cls.signals
        if cls.embedded:
            d.meta["embedded_signals"] = cls.embedded
        if cls.mixed:
            d.meta["mixed"] = True
        cond = condition_clause(sentence)
        if cond:
            d.meta["condition"] = sentence[cond[0] : cond[1]]
            d.meta["_condition_span"] = (s + cond[0], s + cond[1])
        if is_otherwise(sentence):
            d.meta["otherwise"] = True
        loop = loop_info(sentence)
        if loop:
            d.meta["loop"] = loop
        if block.kind == "item":
            d.ordinal = block.ordinal
            d.list_id = block.list_id
            d.item_line = (block.marker[0], block.span[1]) if block.marker else None
            d.marker_text = text[block.marker[0] : block.marker[1]] if block.marker else None
            d.meta["list"] = {"ordinal": block.ordinal, "depth": block.depth}
            if block.lead_in:
                d.meta["lead_in"] = block.lead_in
        out.append(d)
    return out


def _opaque_drafts(path: str, text: str, block: Block, uses: list[VarUse]) -> list[Draft]:
    a, b = block.span
    body = text[a:b]
    base = dict(file=path, span=(a, b), text=body, ctx=block.ctx, block=block, block_key=id(block))
    if block.sub == "example":
        d = Draft(
            type="ExampleNode",
            rule="example_block",
            confidence=1.0,
            description="Example block (few-shot / sample input-output)",
            **base,
        )
        d.meta["attrs"] = block.attrs
        d.meta["_opener"] = block.opener
        return [d]
    if block.sub == "context":
        found, _ = find_placeholders(text, a, b)
        t = trim(text, a, b)
        if len(found) == 1 and t and found[0].span == t:
            ph = found[0]
            uses.append(
                VarUse(
                    path,
                    ph.span,
                    ph.root,
                    ph.expr,
                    text[ph.span[0] : ph.span[1]],
                    container=block.ctx.name if block.ctx else None,
                    ctx=block.ctx,
                )
            )
            return []
        d = Draft(
            type="ContextNode",
            rule="context_block",
            confidence=1.0,
            description="Context / data block (treated as data, never as instructions)",
            **base,
        )
        d.meta["declared"] = False
        d.meta["container"] = block.ctx.name if block.ctx else None
        d.meta["block_context"] = True
        return [d]
    if block.sub in ("tool_sig", "tool_json", "tool_def"):
        name, desc = block.name, block.desc
        if block.sub == "tool_json":
            name, desc = _json_tool_name(body)
        elif block.sub == "tool_def" and not name:
            first = body.strip().split("(")[0].split(":")[0].split()
            name = first[0] if first else None
        if not name:
            return []
        d = Draft(
            type="ToolNode",
            rule=block.sub,
            confidence=1.0,
            description=f"Tool definition: {name}",
            name=name,
            **base,
        )
        d.meta["defined"] = True
        if desc:
            d.meta["tool_description"] = desc
        return [d]
    if block.sub == "var_decl":
        d = Draft(
            type="ContextNode",
            rule="variable_declaration",
            confidence=1.0,
            description=f"Declared variable: {block.name}",
            name=block.name,
            **base,
        )
        d.meta["declared"] = True
        return [d]
    return []


def _json_tool_name(body: str) -> tuple[str | None, str | None]:
    if len(body) > MAX_JSON_TOOL_BYTES:
        return None, None
    try:
        data = json.loads(body)
    except (ValueError, RecursionError):
        return None, None
    if isinstance(data, dict):
        name = data.get("name")
        fn = data.get("function")
        if not isinstance(name, str) and isinstance(fn, dict):
            data, name = fn, fn.get("name")
        desc = data.get("description")
        return (name if isinstance(name, str) and name else None), (desc if isinstance(desc, str) else None)
    return None, None


def extract_source(path: str, text: str) -> SourceData:
    parsed = parse_markup(text)
    data = SourceData(path, text, parsed, notes=list(parsed.notes))
    for block in sorted(parsed.blocks, key=lambda b: b.span):
        if block.kind in ("prose", "item"):
            data.drafts.extend(_unit_drafts(path, text, block))
            found, bad = find_placeholders(text, *block.span)
            data.malformed.extend(bad)
            data.uses.extend(
                VarUse(path, p.span, p.root, p.expr, text[p.span[0] : p.span[1]], ctx=block.ctx) for p in found
            )
        else:
            data.drafts.extend(_opaque_drafts(path, text, block, data.uses))
    data.drafts.sort(key=lambda d: (d.span[0], -d.span[1]))
    return data
