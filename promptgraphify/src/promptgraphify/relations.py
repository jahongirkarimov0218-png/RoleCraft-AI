"""Edge construction over node drafts (ANALYSIS_SPEC §5). Every rule here is deterministic and cites
either an explicit reference (EXTRACTED) or a named rule with confidence < 1 (INFERRED / AMBIGUOUS).

Rule order matters only for suppression: an INFERRED edge is dropped when an EXTRACTED edge with the
same relation and endpoints exists.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .extract import Draft, SourceData, VarUse
from .markup import Container
from .signals import SIGNALS, fold
from .text import Interval, words

Evidence = tuple[str, Interval]
UNIT_TYPES = ("TaskNode", "ConstraintNode", "SystemNode")
ID_SHAPED = re.compile(r"_|[a-z][A-Z]|\d")
NAME_TOKEN = re.compile(r"`?([A-Za-z_][\w.\-]*)`?")
QUOTED = re.compile(r"[\"“«]([^\"”»\n]{2,60})[\"”»]")


@dataclass(eq=False)
class DraftEdge:
    source: Draft
    target: Draft
    relation: str
    status: str
    evidence: list[Evidence]
    rationale: str
    reference: str | None = None
    rule: str | None = None
    confidence: float = 1.0
    meta: dict = field(default_factory=dict)
    method: str = "deterministic:reference"


@dataclass
class Finding:
    kind: str  # unresolved_step | undefined_tool | malformed_template | unclosed (parse notes) ...
    file: str
    span: Interval
    message: str
    draft: Draft | None = None


@dataclass
class Linked:
    drafts: list[Draft]
    edges: list[DraftEdge]
    findings: list[Finding]


def _within(d: Draft, c: Container) -> bool:
    return d.ctx is not None and c in d.ctx.chain()


def _scope_container(d: Draft) -> Container | None:
    """Nearest enclosing container that is not a constraint group (ANALYSIS_SPEC §5, Scope)."""
    c = d.ctx
    while c is not None and "group" in c.flags:
        c = c.parent
    return c


def _is_global(scope: Container | None) -> bool:
    return scope is None or any(c.role for c in scope.chain())


def link(sources: list[SourceData]) -> Linked:
    drafts: list[Draft] = [d for s in sources for d in s.drafts]
    edges: list[DraftEdge] = []
    findings: list[Finding] = []
    {s.path: s for s in sources}

    for s in sources:
        for note in s.notes:
            findings.append(Finding("parse_note:" + note.kind, s.path, note.span, note.message))
        for m in s.malformed:
            findings.append(Finding("malformed_template:" + m.kind, s.path, m.span, f"malformed template ({m.kind})"))

    def emit(
        src,
        tgt,
        relation,
        status,
        evidence,
        rationale,
        *,
        reference=None,
        rule=None,
        confidence=None,
        meta=None,
        method=None,
    ):
        if confidence is None:
            confidence = 1.0 if status == "EXTRACTED" else 0.7
        edges.append(
            DraftEdge(
                src,
                tgt,
                relation,
                status,
                evidence,
                rationale,
                reference,
                rule,
                confidence,
                meta or {},
                method or ("deterministic:reference" if status == "EXTRACTED" else f"deterministic:{rule}"),
            )
        )

    var_drafts = _link_variables(sources, drafts, edges, emit, findings)
    tool_drafts = _link_tools(sources, drafts, emit, findings)
    drafts.extend(var_drafts)
    drafts.extend(tool_drafts)
    drafts.sort(key=lambda d: (d.file, d.span[0], -d.span[1]))

    units = [d for d in drafts if d.type in UNIT_TYPES]
    _link_steps(sources, drafts, emit, findings)
    _link_sequence_and_otherwise(drafts, edges, emit)
    _link_context_mentions(drafts, emit)
    _link_quoted_sections(drafts, emit)
    _link_handoffs(sources, drafts, emit)
    _link_scope(drafts, emit)
    _link_examples(sources, drafts, emit)
    _link_conflicts(units, emit)

    return Linked(drafts, _suppress(edges), findings)


def _suppress(edges: list[DraftEdge]) -> list[DraftEdge]:
    extracted = {(e.relation, id(e.source), id(e.target)) for e in edges if e.status == "EXTRACTED"}
    seen: set[tuple] = set()
    out = []
    for e in edges:
        key = (e.relation, id(e.source), id(e.target))
        if e.status != "EXTRACTED" and key in extracted:
            continue
        full = (*key, e.status, e.rule, tuple(e.evidence))
        if full in seen:
            continue
        seen.add(full)
        out.append(e)
    return out


# ------------------------------------------------------------------------------------------ variables
def _link_variables(sources, drafts, edges, emit, findings) -> list[Draft]:
    declared: dict[str, Draft] = {}
    for d in drafts:
        if d.type == "ContextNode" and d.meta.get("declared") and d.name and d.name not in declared:
            declared[d.name] = d
    uses: list[VarUse] = [u for s in sources for u in s.uses]
    uses.sort(key=lambda u: (u.file, u.span))
    units = [d for d in drafts if d.type in UNIT_TYPES or d.type == "ExampleNode"]
    for u in uses:
        inside = [d for d in units if d.file == u.file and d.span[0] <= u.span[0] and u.span[1] <= d.span[1]]
        if inside:
            u.unit = min(inside, key=lambda d: d.span[1] - d.span[0])
            before = u.unit.text[max(0, u.span[0] - u.unit.span[0] - 60) : u.span[0] - u.unit.span[0]]
            after = u.unit.text[u.span[1] - u.unit.span[0] :]
            u.produced = u.unit.type == "TaskNode" and (
                SIGNALS.has("produce_before", before) or SIGNALS.has("produce_after", after)
            )

    created: dict[str, Draft] = {}
    for u in uses:
        var = declared.get(u.root) or created.get(u.root)
        if var is None:
            var = Draft(
                file=u.file,
                type="ContextNode",
                span=u.span,
                text=u.text,
                ctx=u.ctx,
                rule="variable_placeholder",
                confidence=1.0,
                description=f"Template variable {u.root} (used, never declared)",
                name=u.root,
                meta={"declared": False, "container": u.container},
            )
            created[u.root] = var
        var.meta.setdefault("_uses", []).append(u)
        if u.produced:
            var.meta["produced"] = True
        if u.container and not var.meta.get("container"):
            var.meta["container"] = u.container
    for var in [*declared.values(), *created.values()]:
        var.meta["usage_spans"] = [[u.file, u.span[0], u.span[1]] for u in var.meta.get("_uses", [])]
        var.meta.setdefault("produced", False)

    groups: dict[tuple[int, str], list[VarUse]] = {}
    order: list[tuple[int, str]] = []
    for u in uses:
        if u.unit is None:
            continue
        key = (id(u.unit), u.root)
        if key not in groups:
            order.append(key)
        groups.setdefault(key, []).append(u)
    for key in order:
        group = groups[key]
        unit = group[0].unit
        var = declared.get(group[0].root) or created[group[0].root]
        plain = [u for u in group if not u.produced]
        produced = [u for u in group if u.produced]
        ev = [(unit.file, unit.span)]
        if plain:
            if unit.type == "TaskNode":
                emit(
                    unit,
                    var,
                    "DEPENDS_ON",
                    "EXTRACTED",
                    ev,
                    f"The task uses the variable {plain[0].text}",
                    reference=plain[0].text,
                )
            elif unit.type == "ConstraintNode":
                emit(
                    unit,
                    var,
                    "CONSTRAINS",
                    "EXTRACTED",
                    ev,
                    f"The constraint mentions the variable {plain[0].text}",
                    reference=plain[0].text,
                )
            else:
                emit(
                    unit,
                    var,
                    "REFERENCES",
                    "EXTRACTED",
                    ev,
                    f"The statement mentions the variable {plain[0].text}",
                    reference=plain[0].text,
                )
        if produced:
            emit(
                unit,
                var,
                "PRODUCES",
                "EXTRACTED",
                ev,
                f"The task stores its result in {produced[0].text}",
                reference=produced[0].text,
            )
        cspan = unit.meta.get("_condition_span")
        if cspan and unit.type == "TaskNode":
            gate = [u for u in group if cspan[0] <= u.span[0] and u.span[1] <= cspan[1]]
            if gate:
                emit(
                    var,
                    unit,
                    "CONDITIONALLY_EXECUTES",
                    "EXTRACTED",
                    ev,
                    f"The task runs only if the condition on {gate[0].text} holds",
                    reference=gate[0].text,
                    meta={"condition": unit.meta["condition"]},
                )
    return list(created.values())


# ----------------------------------------------------------------------------------------------- tools
def _id_shaped(name: str, backticked: bool) -> bool:
    return backticked or bool(ID_SHAPED.search(name))


def _link_tools(sources, drafts, emit, findings) -> list[Draft]:
    defined: dict[str, Draft] = {}
    for d in drafts:
        if d.type == "ToolNode" and d.name and d.name not in defined:
            defined[d.name] = d
    var_names = {u.root for s in sources for u in s.uses}
    created: dict[str, Draft] = {}
    mentions: list[tuple[Draft, str, Interval, bool]] = []  # (unit, name, absolute span, defined?)
    for unit in (d for d in drafts if d.type in UNIT_TYPES):
        text = unit.text
        names_here: dict[str, Interval] = {}
        for name in defined:
            m = re.search(rf"(?<![\w]){re.escape(name)}(?![\w])", text)
            if m:
                names_here[name] = (unit.span[0] + m.start(), unit.span[0] + m.end())
        if unit.type in ("TaskNode", "ConstraintNode"):
            cands: list[tuple[str, int, int, bool]] = []
            for hit in SIGNALS.find_all("call_verbs", text):
                rest = text[hit.end :]
                lead = re.match(r"\s+(?:(?:the|a|an)\s+)?", rest)
                if not lead:
                    continue
                m = NAME_TOKEN.match(rest, lead.end())
                if m:
                    cands.append(
                        (
                            m.group(1),
                            hit.end + m.start(1),
                            hit.end + m.end(1),
                            rest[m.start() : m.start() + 1] == "`",
                        )
                    )
            for hit in SIGNALS.find_all("tool_mention", text):
                if hit.groups and hit.groups[0]:
                    g = hit.groups[0]
                    cands.append((g, hit.start + hit.text.index(g), hit.start + hit.text.index(g) + len(g), False))
            for name, a, _b, bt in cands:
                name = name.rstrip(".-")
                if name in defined or name in var_names or name in names_here or not _id_shaped(name, bt):
                    continue
                names_here[name] = (unit.span[0] + a, unit.span[0] + a + len(name))
        for name, span in names_here.items():
            tool = defined.get(name)
            if tool is None:
                tool = created.get(name)
                if tool is None:
                    tool = Draft(
                        file=unit.file,
                        type="ToolNode",
                        span=span,
                        text=name,
                        ctx=unit.ctx,
                        rule="tool_reference",
                        confidence=0.7,
                        description=f"Tool {name} is referenced but never defined",
                        name=name,
                        meta={"defined": False},
                    )
                    created[name] = tool
            mentions.append((unit, name, span, tool.meta.get("defined", False)))
    for unit, name, span, is_defined in mentions:
        tool = defined.get(name) or created[name]
        ev = [(unit.file, unit.span)]
        tool.meta.setdefault("mentioned_by", 0)
        tool.meta["mentioned_by"] += 1
        if unit.type == "TaskNode":
            if is_defined:
                emit(
                    unit,
                    tool,
                    "CALLS_TOOL",
                    "EXTRACTED",
                    ev,
                    f"The task names the tool {name}",
                    reference=name,
                )
            else:
                emit(
                    unit,
                    tool,
                    "CALLS_TOOL",
                    "AMBIGUOUS",
                    ev,
                    f"The task calls {name}, which is never defined",
                    reference=name,
                    confidence=0.5,
                    rule="tool.unresolved",
                    meta={"candidates": []},
                    method="deterministic:tool.unresolved",
                )
                findings.append(Finding("undefined_tool", unit.file, span, f"{name} is called but never defined", tool))
        elif unit.type == "ConstraintNode":
            emit(
                unit,
                tool,
                "CONSTRAINS",
                "EXTRACTED",
                ev,
                f"The constraint names the tool {name}",
                reference=name,
            )
        else:
            emit(
                unit,
                tool,
                "REFERENCES",
                "EXTRACTED",
                ev,
                f"The statement names the tool {name}",
                reference=name,
            )
    return list(created.values())


# ------------------------------------------------------------------------------- numbered steps, loops
def _link_steps(sources, drafts, emit, findings) -> None:
    items: dict[tuple[str, int], dict[int, list[Draft]]] = {}
    for d in drafts:
        if d.list_id is not None and d.ordinal is not None:
            items.setdefault((d.file, d.list_id), {}).setdefault(d.ordinal, []).append(d)

    # consecutive numbered items -> PRECEDES
    for (_, _), by_ord in items.items():
        keys = sorted(by_ord, key=lambda k: min(x.span[0] for x in by_ord[k]))
        for a, b in zip(keys, keys[1:], strict=False):
            if b != a + 1:
                continue
            src_tasks = [x for x in by_ord[a] if x.type == "TaskNode"]
            tgt_tasks = [x for x in by_ord[b] if x.type == "TaskNode"]
            if not src_tasks or not tgt_tasks:
                continue
            src, tgt = src_tasks[-1], tgt_tasks[0]
            if src.item_line and tgt.item_line:
                emit(
                    src,
                    tgt,
                    "PRECEDES",
                    "EXTRACTED",
                    [(src.file, src.item_line), (tgt.file, tgt.item_line)],
                    f"Item {tgt.marker_text} follows item {src.marker_text} in a numbered list",
                    reference=tgt.marker_text,
                )

    # explicit "step N" references
    for d in (x for x in drafts if x.type == "TaskNode"):
        for hit in SIGNALS.find_all("step_ref", d.text):
            n = next((int(g) for g in hit.groups if g), None)
            if n is None:
                continue
            by_ord = items.get((d.file, d.list_id)) if d.list_id is not None else None
            if by_ord is None:
                candidates = [v for (f, _), v in items.items() if f == d.file]
                by_ord = candidates[0] if len(candidates) == 1 else None
            targets = [t for t in (by_ord or {}).get(n, []) if t.type == "TaskNode"]
            loop_back = SIGNALS.find("loop_back", d.text[: hit.start + 1]) is not None
            ev = [(d.file, d.span)]
            if not targets:
                findings.append(
                    Finding(
                        "unresolved_step",
                        d.file,
                        (d.span[0] + hit.start, d.span[0] + hit.end),
                        f"{hit.text} does not exist",
                        d,
                    )
                )
                continue
            tgt = targets[0]
            if loop_back:
                loop = d.meta.get("loop") or {"stop_condition": None}
                emit(
                    d,
                    tgt,
                    "PRECEDES",
                    "EXTRACTED",
                    ev,
                    f"The task repeats from {hit.text}",
                    reference=hit.text,
                    meta={"loop": True, "stop_condition": loop.get("stop_condition")},
                )
            elif tgt is d or tgt.block_key == d.block_key:
                emit(
                    d,
                    d,
                    "DEPENDS_ON",
                    "EXTRACTED",
                    ev,
                    f"The task refers to its own step ({hit.text})",
                    reference=hit.text,
                    meta={"self_reference": True},
                )
            else:
                emit(
                    d,
                    tgt,
                    "DEPENDS_ON",
                    "EXTRACTED",
                    ev,
                    f"The task depends on the result of {hit.text}",
                    reference=hit.text,
                )


def _link_sequence_and_otherwise(drafts, edges, emit) -> None:
    tasks = [d for d in drafts if d.type == "TaskNode"]
    for i, d in enumerate(tasks):
        if SIGNALS.has("sequence_words", d.text) and i > 0:
            prev = tasks[i - 1]
            if prev.file == d.file and prev.ctx is d.ctx:
                emit(
                    prev,
                    d,
                    "PRECEDES",
                    "INFERRED",
                    [(prev.file, prev.span), (d.file, d.span)],
                    "A sequence word at the start links this unit to the previous one",
                    rule="sequence.word",
                    confidence=0.7,
                )
    for d in tasks:
        if not d.meta.get("otherwise"):
            continue
        prev_edges = [
            e
            for e in edges
            if e.relation == "CONDITIONALLY_EXECUTES"
            and e.target.file == d.file
            and e.target.span[1] <= d.span[0]
            and e.target.type == "TaskNode"
        ]
        if not prev_edges:
            continue
        last = max(prev_edges, key=lambda e: e.target.span[0])
        cond = last.meta.get("condition", "")
        emit(
            last.source,
            d,
            "CONDITIONALLY_EXECUTES",
            "INFERRED",
            [(d.file, d.span)],
            "The unit starts with 'otherwise' after a conditional unit",
            rule="condition.otherwise",
            confidence=0.8,
            meta={"condition": f"not ({cond})"},
        )


# -------------------------------------------------------------------------- context blocks, sections
def _link_context_mentions(drafts, emit) -> None:
    ctx_nodes = [d for d in drafts if d.type == "ContextNode" and d.meta.get("container")]
    for t in (d for d in drafts if d.type == "TaskNode"):
        for c in ctx_nodes:
            name = c.meta["container"]
            m = re.search(rf"<\s*/?\s*{re.escape(name)}\s*/?>", t.text, flags=re.IGNORECASE)
            if m:
                emit(
                    c,
                    t,
                    "PROVIDES_CONTEXT",
                    "EXTRACTED",
                    [(t.file, t.span)],
                    f"The task names the data block {m.group(0)}",
                    reference=m.group(0),
                )


def _containers(drafts) -> dict[str, list[Container]]:
    seen: dict[str, list[Container]] = {}
    ids: set[int] = set()
    for d in drafts:
        for c in d.ctx.chain() if d.ctx else []:
            if id(c) not in ids:
                ids.add(id(c))
                seen.setdefault(fold(c.name).lower(), []).append(c)
    return seen


def _link_quoted_sections(drafts, emit) -> None:
    by_name = _containers(drafts)
    for u in (d for d in drafts if d.type in UNIT_TYPES):
        overrides = SIGNALS.has("hierarchy", u.text)
        for m in QUOTED.finditer(u.text):
            for c in by_name.get(fold(m.group(1)).strip().lower(), []):
                if u.ctx is not None and c in u.ctx.chain():
                    continue
                targets = [
                    t for t in drafts if t is not u and t.file == u.file and _within(t, c) and t.type != "ExampleNode"
                ]
                for t in targets:
                    ev = [(u.file, u.span)]
                    if overrides and u.type == "SystemNode" and t.type in ("SystemNode", "ConstraintNode", "TaskNode"):
                        emit(
                            u,
                            t,
                            "OVERRIDES",
                            "EXTRACTED",
                            ev,
                            f"The statement takes precedence over {m.group(0)}",
                            reference=m.group(0),
                        )
                    elif t.type == "ContextNode" and u.type == "TaskNode":
                        emit(
                            t,
                            u,
                            "PROVIDES_CONTEXT",
                            "EXTRACTED",
                            ev,
                            f"The task names the section {m.group(0)}",
                            reference=m.group(0),
                        )
                    elif not overrides:
                        emit(
                            u,
                            t,
                            "REFERENCES",
                            "EXTRACTED",
                            ev,
                            f"The unit names the section {m.group(0)}",
                            reference=m.group(0),
                        )


# -------------------------------------------------------------------------------------------- handoffs
def _link_handoffs(sources, drafts, emit) -> None:
    agents = {fold(d.agent).lower(): d.agent for d in drafts if d.agent}
    files = {s.path: s for s in sources}
    tasks = [d for d in drafts if d.type == "TaskNode"]
    for u in tasks:
        hit = SIGNALS.find("handoff", u.text)
        if not hit:
            continue
        rest = fold(u.text[hit.end :]).lower()
        target_file = None
        for path in sorted(files, key=len, reverse=True):
            base = path.rsplit("/", 1)[-1].lower()
            if base in rest and path != u.file:
                target_file = path
                break
        target_tasks: list[Draft] = []
        if target_file:
            target_tasks = [t for t in tasks if t.file == target_file]
        else:
            for low, name in agents.items():
                if re.search(rf"(?<![\w]){re.escape(low)}(?![\w])", rest) and name != u.agent:
                    target_tasks = [t for t in tasks if t.agent == name]
                    break
        if target_tasks:
            tgt = min(target_tasks, key=lambda t: (t.file, t.span[0]))
            if tgt is not u:
                emit(
                    u,
                    tgt,
                    "PRECEDES",
                    "INFERRED",
                    [(u.file, u.span), (tgt.file, tgt.span)],
                    "A hand-off statement names the target; its first task follows",
                    rule="handoff.first_task",
                    confidence=0.75,
                )


# --------------------------------------------------------------------------------------------- scope
def _link_scope(drafts, emit) -> None:
    tasks = [d for d in drafts if d.type == "TaskNode"]
    for c in (d for d in drafts if d.type == "ConstraintNode"):
        scope = _scope_container(c)
        if _is_global(scope):
            c.meta["scope"] = "global"
            continue
        c.meta["scope"] = scope.name
        for t in tasks:
            if t.file == c.file and _within(t, scope):
                emit(
                    c,
                    t,
                    "CONSTRAINS",
                    "INFERRED",
                    [(c.file, c.span), (t.file, t.span)],
                    f"The constraint and the task share the section {scope.name!r}",
                    rule="scope.section",
                    confidence=0.8,
                )
    blocks = [d for d in drafts if d.type == "ContextNode" and d.meta.get("block_context")]
    for b in blocks:
        scope = b.ctx.parent if b.ctx else None
        if _is_global(scope):
            continue
        for t in tasks:
            if t.file == b.file and _within(t, scope):
                emit(
                    b,
                    t,
                    "PROVIDES_CONTEXT",
                    "INFERRED",
                    [(b.file, b.span), (t.file, t.span)],
                    f"The data block and the task share the section {scope.name!r}",
                    rule="scope.section",
                    confidence=0.7,
                )


# ------------------------------------------------------------------------------------------ examples
def _link_examples(sources, drafts, emit) -> None:
    tools = {d.name: d for d in drafts if d.type == "ToolNode" and d.name}
    anchors = [d for d in drafts if d.type in ("TaskNode", "ConstraintNode")]
    for ex in (d for d in drafts if d.type == "ExampleNode"):
        opener = ex.meta.get("_opener")
        explicit = False
        if opener:
            text = next(s.text for s in sources if s.path == ex.file)
            tag = text[opener[0] : opener[1]]
            for key, value in (ex.meta.get("attrs") or {}).items():
                if value in tools:
                    m = re.search(rf"{re.escape(key)}\s*=\s*[\"']{re.escape(value)}[\"']", tag)
                    emit(
                        ex,
                        tools[value],
                        "EXEMPLIFIES",
                        "EXTRACTED",
                        [(ex.file, opener)],
                        f"The example tag names the tool {value}",
                        reference=m.group(0) if m else value,
                    )
                    explicit = True
        if explicit:
            continue
        home = ex.ctx.parent if ex.ctx else None
        prior = [
            a for a in anchors if a.file == ex.file and a.span[1] <= ex.span[0] and (home is None or _within(a, home))
        ]
        if home is None:
            prior = [a for a in anchors if a.file == ex.file and a.span[1] <= ex.span[0]]
        if prior:
            # An example normally demonstrates what to do, so the nearest preceding task wins; only if no task
            # precedes it does the nearest preceding constraint (D-022).
            tasks_before = [a for a in prior if a.type == "TaskNode"]
            near = max(tasks_before or prior, key=lambda a: a.span[1])
            emit(
                ex,
                near,
                "EXEMPLIFIES",
                "INFERRED",
                [(ex.file, ex.span), (near.file, near.span)],
                "The example follows this instruction in the same container",
                rule="proximity.preceding",
                confidence=0.55,
            )


# ------------------------------------------------------------------------------------------ conflicts
def _signature(text: str) -> tuple[str | None, frozenset[str]]:
    neg = SIGNALS.has("prohibition", text)
    pos = SIGNALS.has("obligation", text)
    polarity = "neg" if neg else "pos" if pos else None
    toks = frozenset(w for w, _, _ in words(text) if w not in SIGNALS.stopwords and len(w) > 1)
    return polarity, toks


def _link_conflicts(units, emit) -> None:
    cands = [u for u in units if u.type in ("ConstraintNode", "TaskNode")]
    sigs = {id(u): _signature(u.text) for u in cands}
    for i, a in enumerate(cands):
        for b in cands[i + 1 :]:
            if a.file != b.file or a.agent != b.agent:
                continue
            pa, ta = sigs[id(a)]
            pb, tb = sigs[id(b)]
            if pa is None or pb is None or pa == pb or len(ta) < 2 or len(tb) < 2:
                continue
            jac = len(ta & tb) / len(ta | tb)
            if jac == 1.0:
                emit(
                    a,
                    b,
                    "CONFLICTS_WITH",
                    "INFERRED",
                    [(a.file, a.span), (b.file, b.span)],
                    "Same instruction with opposite polarity (always / never)",
                    rule="conflict.polarity",
                    confidence=0.7,
                )
            elif jac >= 0.6:
                emit(
                    a,
                    b,
                    "CONFLICTS_WITH",
                    "AMBIGUOUS",
                    [(a.file, a.span), (b.file, b.span)],
                    "Similar instructions with opposite polarity",
                    rule="conflict.partial_overlap",
                    confidence=0.5,
                    meta={"overlap": round(jac, 2)},
                )
