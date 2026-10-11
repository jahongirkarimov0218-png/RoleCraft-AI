# ruff: noqa: E501
"""Static analyzer: diagnostics over the knowledge graph, the execution DAG and the source text.

Every rule is registered in ``rules.RULES`` (severity, detection method, certainty) and documented in
docs/ANALYSIS_SPEC.md §7. A semantic finding (conflict, ambiguity, injection) is never ``proven``.
Rule functions are small and independent; each returns zero or more ``Diagnostic`` objects.
"""

from __future__ import annotations

import hashlib
import re
from collections import Counter
from collections.abc import Callable, Iterable
from dataclasses import dataclass

from .dag import unschedulable
from .ids import normalize_text
from .ir import DagView, Diagnostic, Edge, Evidence, GraphDocument, Node, UnresolvedDependency
from .relations import Finding
from .rules import RULES
from .signals import SIGNALS
from .spans import Span


@dataclass
class Facts:
    """Everything a rule may look at."""

    nodes: list[Node]
    edges: list[Edge]
    dag: DagView
    texts: dict[str, str]
    findings: list[tuple[Finding, str | None]]  # (finding, node id of the draft it concerns)
    unresolved: list[UnresolvedDependency]

    def __post_init__(self) -> None:
        self.by_id = {n.id: n for n in self.nodes}
        self.out: dict[str, list[Edge]] = {}
        self.inc: dict[str, list[Edge]] = {}
        for e in self.edges:
            self.out.setdefault(e.source, []).append(e)
            self.inc.setdefault(e.target, []).append(e)

    def label(self, nid: str) -> str:
        n = self.by_id.get(nid)
        return n.label if n else nid

    def ev(self, node: Node) -> Evidence:
        return Evidence(source_file=node.source_file, span=node.source_span, text=node.original_text)

    def ev_span(self, file: str, a: int, b: int) -> Evidence:
        return Evidence(source_file=file, span=Span(start=a, end=b), text=self.texts[file][a:b])

    def smallest_node_at(self, file: str, a: int, b: int) -> Node | None:
        hits = [n for n in self.nodes if n.source_file == file and n.source_span.start <= a and b <= n.source_span.end]
        return min(hits, key=lambda n: n.source_span.end - n.source_span.start) if hits else None


def _make(
    rule_id: str,
    description: str,
    fix: str,
    *,
    nodes: Iterable[str] = (),
    edges: Iterable[str] = (),
    evidence: Iterable[Evidence] = (),
    certainty: str | None = None,
) -> Diagnostic:
    rule = RULES[rule_id]
    nodes, edges, evidence = sorted(set(nodes)), sorted(set(edges)), list(evidence)
    cert = certainty or ("proven" if rule.certainty == "mixed" else rule.certainty)
    key = "|".join([rule_id, *nodes, *edges, *(f"{e.source_file}:{e.span.start}-{e.span.end}" for e in evidence)])
    return Diagnostic(
        id="d_" + hashlib.sha256(key.encode("utf-8")).hexdigest()[:12],
        rule_id=rule_id,
        severity=rule.severity,
        certainty=cert,  # type: ignore[arg-type]
        detection=rule.detection,
        description=description,
        evidence=evidence,
        affected_nodes=nodes,
        affected_edges=edges,
        suggested_fix=fix,
    )


def _short(text: str, n: int = 60) -> str:
    text = " ".join(text.split())
    return text if len(text) <= n else text[: n - 1] + "…"


# ------------------------------------------------------------------------------------------- input / parse
_INVISIBLE = re.compile("[\\s\ufeff\u200b-\u200f\u2060]")  # whitespace, BOM and zero-width marks carry no content


def rule_input_empty(f: Facts) -> list[Diagnostic]:
    if all(not _INVISIBLE.sub("", t) for t in f.texts.values()):
        return [_make("input.empty", "The input contains no text.", "Provide a prompt: at least one non-empty line.")]
    return []


def rule_parse_malformed(f: Facts) -> list[Diagnostic]:
    by_file: dict[str, list[Finding]] = {}
    for fi, _ in f.findings:
        if fi.kind.startswith("parse_note:"):
            by_file.setdefault(fi.file, []).append(fi)
    out = []
    for file, items in sorted(by_file.items()):
        ev = [f.ev_span(file, *fi.span) for fi in sorted(items, key=lambda x: x.span)]
        details = "; ".join(sorted({fi.message for fi in items}))[:300]
        out.append(
            _make(
                "parse.malformed",
                f"{file}: {len(items)} syntax problem(s): {details}",
                "Close or fix the marked tags, fences or brackets; the analysis recovered but spans may be coarser.",
                evidence=ev,
            )
        )
    return out


def rule_template_malformed(f: Facts) -> list[Diagnostic]:
    out = []
    for fi, _ in f.findings:
        if fi.kind.startswith("malformed_template:"):
            kind = fi.kind.split(":", 1)[1]
            out.append(
                _make(
                    "template.malformed",
                    f"Placeholder is malformed ({kind}): {_short(f.texts[fi.file][fi.span[0] : fi.span[1]])}",
                    "Use one well-formed placeholder such as {{name}} per variable; do not nest or leave braces open.",
                    evidence=[f.ev_span(fi.file, *fi.span)],
                )
            )
    return out


# ------------------------------------------------------------------------------------------------ variables
def rule_variables(f: Facts) -> list[Diagnostic]:
    out = []
    for n in f.nodes:
        if n.type != "ContextNode" or n.metadata.get("block_context"):
            continue
        declared = n.metadata.get("declared") is True
        produced = n.metadata.get("produced") is True
        uses = n.metadata.get("usage_spans") or []
        if not declared and not produced and uses:
            out.append(
                _make(
                    "variable.undeclared",
                    f"Variable {n.label} is used but never declared or produced in the analysed input.",
                    f"Declare {n.label} in a Variables section (or YAML/JSON `variables`) or make sure the caller supplies it.",
                    nodes=[n.id],
                    evidence=[f.ev(n)],
                )
            )
        if declared and not uses:
            out.append(
                _make(
                    "variable.unused",
                    f"Variable {n.label} is declared but never used.",
                    f"Use {n.label} where it is needed, or remove the declaration.",
                    nodes=[n.id],
                    evidence=[f.ev(n)],
                )
            )
    return out


# ---------------------------------------------------------------------------------------------------- tools
def rule_tools(f: Facts) -> list[Diagnostic]:
    out = []
    reported: set[str] = set()  # one finding per mention, one diagnostic per tool (the tool node is the evidence)
    for fi, nid in f.findings:
        if fi.kind == "undefined_tool" and nid and nid not in reported:
            reported.add(nid)
            n = f.by_id[nid]
            out.append(
                _make(
                    "tool.undefined",
                    f"{n.label} is called but no tool definition was found.",
                    f"Add a definition for {n.label} (name, parameters) or remove the call.",
                    nodes=[nid],
                    edges=[e.id for e in f.inc.get(nid, []) if e.relation == "CALLS_TOOL"],
                    evidence=[f.ev(n)],
                )
            )
    for n in f.nodes:
        if n.type == "ToolNode" and n.metadata.get("defined") is True and not f.inc.get(n.id) and not f.out.get(n.id):
            out.append(
                _make(
                    "tool.unused",
                    f"Tool {n.label} is defined but never referenced.",
                    f"Call {n.label} from a task, or remove the definition.",
                    nodes=[n.id],
                    evidence=[f.ev(n)],
                )
            )
    # a constraint that prohibits a tool vs a task that calls it
    for n in f.nodes:
        if n.type != "ConstraintNode" or not n.extraction_method.endswith("prohibition"):
            continue
        for e in f.out.get(n.id, []):
            if e.relation == "CONSTRAINS" and f.by_id[e.target].type == "ToolNode":
                for c in f.inc.get(e.target, []):
                    if c.relation == "CALLS_TOOL":
                        task = f.by_id[c.source]
                        out.append(
                            _make(
                                "tool.permission_mismatch",
                                f"A constraint forbids {f.label(e.target)} ({_short(n.original_text)}) while a task calls it ({_short(task.original_text)}).",
                                "Remove the call, or state the exact condition under which the tool may be used.",
                                nodes=[n.id, task.id, e.target],
                                edges=[e.id, c.id],
                                evidence=[f.ev(n), f.ev(task)],
                            )
                        )
    return out


# ------------------------------------------------------------------------------------- dependencies / DAG
def rule_dependencies(f: Facts) -> list[Diagnostic]:
    out = []
    for c in f.dag.cycles:
        names = " → ".join(f.label(v) for v in c.nodes[:6]) + (" …" if len(c.nodes) > 6 else "")
        out.append(
            _make(
                "dependency.cycle",
                f"Circular dependency: {names}. None of these can start before the others.",
                "Break the loop: remove one dependency, or turn it into an explicit repetition with a stop condition.",
                nodes=c.nodes,
                edges=c.edges,
                evidence=c.evidence,
                certainty=c.certainty,
            )
        )
    for fi, nid in f.findings:
        if fi.kind == "unresolved_step" and nid:
            out.append(
                _make(
                    "dependency.unresolved",
                    f"{fi.message}: no such step exists.",
                    "Fix the step number, or add the missing step.",
                    nodes=[nid],
                    evidence=[f.ev_span(fi.file, *fi.span)],
                )
            )
    blocked = [nid for nid in unschedulable(f.nodes, f.edges, f.unresolved) if f.by_id[nid].type == "TaskNode"]
    if blocked:
        proven = all(c.certainty == "proven" for c in f.dag.cycles)
        out.append(
            _make(
                "task.unreachable",
                f"{len(blocked)} task(s) can never be scheduled: they lie on or behind a circular or unresolved dependency.",
                "Resolve the cycle or the missing dependency listed in the other diagnostics.",
                nodes=blocked,
                evidence=[f.ev(f.by_id[b]) for b in blocked],
                certainty="proven" if proven else "probable",
            )
        )
    return out


def rule_orphans(f: Facts) -> list[Diagnostic]:
    orphans = []
    for n in f.nodes:
        if f.inc.get(n.id) or f.out.get(n.id):
            continue
        if n.type in ("ContextNode", "ToolNode", "ExampleNode"):
            orphans.append(n)
        elif n.type == "ConstraintNode" and n.metadata.get("scope") not in (None, "global"):
            orphans.append(n)
    if not orphans:
        return []
    return [
        _make(
            "node.orphan",
            f"{len(orphans)} node(s) have no relation to anything else: {', '.join(_short(n.label, 30) for n in orphans[:5])}.",
            "Reference them from a task, or remove them if they are leftovers.",
            nodes=[n.id for n in orphans],
            evidence=[f.ev(n) for n in orphans],
        )
    ]


# ------------------------------------------------------------------------------------- semantic findings
def rule_duplicates(f: Facts) -> list[Diagnostic]:
    groups: dict[tuple, list[Node]] = {}
    for n in f.nodes:
        if n.type in ("TaskNode", "ConstraintNode", "SystemNode"):
            groups.setdefault((n.type, normalize_text(n.decoded_text or n.original_text)), []).append(n)
    return [
        _make(
            "instruction.duplicate",
            f"The same instruction appears {len(g)} times: {_short(g[0].original_text)}",
            "Keep one copy.",
            nodes=[n.id for n in g],
            evidence=[f.ev(n) for n in g],
        )
        for g in groups.values()
        if len(g) > 1
    ]


def rule_conflicts(f: Facts) -> list[Diagnostic]:
    out = []
    for e in f.edges:
        if e.relation == "CONFLICTS_WITH":
            a, b = f.by_id[e.source], f.by_id[e.target]
            how = (
                "state the same instruction with opposite polarity"
                if e.status == "INFERRED"
                else "look contradictory (partial overlap)"
            )
            out.append(
                _make(
                    "constraint.conflict",
                    f"Two instructions {how}: “{_short(a.original_text, 40)}” and “{_short(b.original_text, 40)}”.",
                    "Decide which one applies, or scope them to different situations.",
                    nodes=[a.id, b.id],
                    edges=[e.id],
                    evidence=[f.ev(a), f.ev(b)],
                )
            )
    return out


def rule_role_conflict(f: Facts) -> list[Diagnostic]:
    groups: dict[tuple, list[Node]] = {}
    for n in f.nodes:
        if n.type == "SystemNode" and n.extraction_method.endswith("identity"):
            groups.setdefault((n.source_file, n.role_scope.role, n.role_scope.agent), []).append(n)
    out = []
    for g in groups.values():
        if len({normalize_text(n.original_text) for n in g}) > 1:
            out.append(
                _make(
                    "role.conflict",
                    f"{len(g)} different identities are assigned in one scope: "
                    + " / ".join(_short(n.original_text, 30) for n in g[:3]),
                    "Keep a single identity per agent or message role.",
                    nodes=[n.id for n in g],
                    evidence=[f.ev(n) for n in g],
                )
            )
    return out


def rule_ambiguous(f: Facts) -> list[Diagnostic]:
    hits: list[tuple[Node, list[str]]] = []
    for n in f.nodes:
        if n.type not in ("TaskNode", "ConstraintNode"):
            continue
        text = n.decoded_text or n.original_text
        found = SIGNALS.find_all("vague", text)
        if found and not any(ch.isdigit() for ch in text):
            hits.append((n, sorted({h.text.lower() for h in found})))
    if not hits:
        return []
    terms = sorted({t for _, ts in hits for t in ts})
    return [
        _make(
            "instruction.ambiguous",
            f"{len(hits)} instruction(s) use vague wording without a measurable criterion ({', '.join(terms[:6])}).",
            "Replace vague words with something checkable: a number, a format, or an example.",
            nodes=[n.id for n, _ in hits],
            evidence=[f.ev(n) for n, _ in hits],
        )
    ]


def rule_contract(f: Facts) -> list[Diagnostic]:
    out = []
    has_task = any(n.type == "TaskNode" for n in f.nodes)
    if not has_task:
        return out
    spec = any(
        n.type == "ConstraintNode" and SIGNALS.has("output_spec", n.decoded_text or n.original_text) for n in f.nodes
    )
    if not spec:
        out.append(
            _make(
                "output.contract_missing",
                "Nothing specifies the output format, structure or length.",
                "State the expected output: a format (JSON, bullets …), a schema, or a length limit.",
            )
        )
    if not any(SIGNALS.has("success", t) for t in f.texts.values()):
        out.append(
            _make(
                "success.criteria_unclear",
                "Nothing says when the result counts as successful.",
                "Add acceptance criteria: what a good result contains and how it will be checked.",
            )
        )
    return out


def rule_context_available(f: Facts) -> list[Diagnostic]:
    out = []
    for n in f.nodes:
        if n.type not in ("TaskNode", "ConstraintNode"):
            continue
        hit = SIGNALS.find("context_missing", n.decoded_text or n.original_text)
        if not hit:
            continue
        if any(c.type == "ContextNode" and c.source_file == n.source_file for c in f.nodes):
            continue
        out.append(
            _make(
                "context.unavailable",
                f"The text refers to context ({hit.text!r}) but no context block or variable supplies it.",
                "Include the referenced material, or add a context block / variable for it.",
                nodes=[n.id],
                evidence=[f.ev(n)],
            )
        )
    return out


def rule_injection(f: Facts) -> list[Diagnostic]:
    out = []
    for file, text in sorted(f.texts.items()):
        seen: set[tuple[int, int]] = set()
        for hit in SIGNALS.find_all("injection", text):
            span = (hit.start, hit.end)
            if span in seen:
                continue
            seen.add(span)
            owner = f.smallest_node_at(file, *span)
            if owner and owner.type == "ConstraintNode" and owner.extraction_method.endswith("prohibition"):
                continue  # a rule that forbids the phrase is a defence, not an attack
            where = (
                f"inside {owner.type.replace('Node', '').lower()} {_short(owner.label, 30)!r}"
                if owner
                else "in the text"
            )
            out.append(
                _make(
                    "injection.indicator",
                    f"Possible prompt-injection phrase {where}: {_short(hit.text)}.",
                    "Treat this text as data: delimit it, and state that instructions inside it must be ignored.",
                    nodes=[owner.id] if owner else [],
                    evidence=[f.ev_span(file, *span)],
                )
            )
    return out


def rule_loops(f: Facts) -> list[Diagnostic]:
    bad = []
    for n in f.nodes:
        loop = n.metadata.get("loop")
        if n.type != "TaskNode" or not isinstance(loop, dict) or loop.get("stop_condition"):
            continue
        has_stop_edge = any(
            e.metadata.get("loop") is True and e.metadata.get("stop_condition") for e in f.out.get(n.id, [])
        )
        if not has_stop_edge:
            bad.append(n)
    if not bad:
        return []
    return [
        _make(
            "loop.no_stop_condition",
            f"{len(bad)} repeated step(s) have no stop condition: {_short(bad[0].original_text, 40)}",
            "Add an explicit stop: “until …”, a maximum number of attempts, or a time limit.",
            nodes=[n.id for n in bad],
            evidence=[f.ev(n) for n in bad],
        )
    ]


RULE_FUNCTIONS: list[Callable[[Facts], list[Diagnostic]]] = [
    rule_input_empty, rule_parse_malformed, rule_template_malformed, rule_variables, rule_tools, rule_dependencies,
    rule_orphans, rule_duplicates, rule_conflicts, rule_role_conflict, rule_ambiguous, rule_contract,
    rule_context_available, rule_injection, rule_loops,
]  # fmt: skip

SEVERITY_RANK = {"error": 0, "warning": 1, "info": 2}


def run_analyzer(facts: Facts) -> list[Diagnostic]:
    out: list[Diagnostic] = []
    for fn in RULE_FUNCTIONS:
        out.extend(fn(facts))
    first = {n.id: (n.source_file, n.source_span.start) for n in facts.nodes}

    def order(d: Diagnostic):
        pos = min((first[n] for n in d.affected_nodes if n in first), default=("", -1))
        return (SEVERITY_RANK[d.severity], d.rule_id, pos, d.id)

    return sorted(out, key=order)


def implemented_rules() -> set[str]:
    """Rule ids that have an implementation (a rule listed in RULES but missing here is unfinished)."""
    return {
        "input.empty", "parse.malformed", "template.malformed", "variable.undeclared", "variable.unused",
        "tool.undefined", "tool.unused", "tool.permission_mismatch", "dependency.cycle", "dependency.unresolved",
        "task.unreachable", "node.orphan", "instruction.duplicate", "constraint.conflict", "role.conflict",
        "instruction.ambiguous", "output.contract_missing", "success.criteria_unclear", "context.unavailable",
        "injection.indicator", "loop.no_stop_condition",
    }  # fmt: skip


def analyze_document(doc: GraphDocument, findings: list[tuple[Finding, str | None]]) -> list[Diagnostic]:
    """Convenience for tests: run the analyzer on a finished document."""
    texts = {s.path: s.text for s in doc.sources}
    return run_analyzer(Facts(doc.nodes, doc.edges, doc.dag, texts, findings, doc.dag.unresolved))


MAX_PER_RULE = 200


def cap_per_rule(diagnostics: list[Diagnostic], limit: int = MAX_PER_RULE) -> tuple[list[Diagnostic], list[str]]:
    """At most ``limit`` diagnostics per rule, in the order given, plus one warning per rule that was cut. A hostile
    or generated prompt can trigger a rule hundreds of thousands of times; the cut is reported, never silent."""
    kept: list[Diagnostic] = []
    seen: Counter[str] = Counter()
    for d in diagnostics:
        seen[d.rule_id] += 1
        if seen[d.rule_id] <= limit:
            kept.append(d)
    warnings = [
        f"diagnostics: {n - limit} more {rule} finding(s) are not listed (limit {limit} per rule, {n} found)"
        for rule, n in sorted(seen.items())
        if n > limit
    ]
    return kept, warnings
