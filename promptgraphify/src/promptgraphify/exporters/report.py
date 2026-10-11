"""GRAPH_REPORT.md: a human-readable summary of one analysis. Every number states what it counts; every
label is shown inside a code span so Markdown or HTML in a prompt cannot change the report's structure."""

from __future__ import annotations

import re
from collections import Counter

from ..ir import Diagnostic, Edge, GraphDocument, Node
from ..security import sanitize_label

DEGREE_DEFINITION = "degree = number of knowledge-graph edges that start or end at the node (a self-loop counts once)."
TOP_N = 10


def _code(text: str, limit: int = 120) -> str:
    """Inline code span that survives any content (fence one backtick longer than the longest run inside)."""
    t = sanitize_label(text)
    if len(t) > limit:
        t = t[: limit - 1].rstrip() + "…"
    runs = [len(m) for m in re.findall(r"`+", t)]
    fence = "`" * (max(runs, default=0) + 1)
    pad = " " if t.startswith("`") or t.endswith("`") else ""
    return f"{fence}{pad}{t}{pad}{fence}"


def _node(n: Node) -> str:
    return f"{_code(n.label)} ({n.type})"


def _degree(doc: GraphDocument) -> Counter[str]:
    deg: Counter[str] = Counter()
    for e in doc.edges:
        deg[e.source] += 1
        if e.target != e.source:
            deg[e.target] += 1
    return deg


def _where(n: Node) -> str:
    return f"{_code(n.source_file, 80)} [{n.source_span.start}, {n.source_span.end})"


def _diag_line(d: Diagnostic, by_id: dict[str, Node]) -> str:
    names = ", ".join(_code(by_id[i].label, 60) for i in d.affected_nodes if i in by_id)
    quote = f" — evidence: {_code(d.evidence[0].text, 100)}" if d.evidence else ""
    where = f" ({names})" if names else ""
    return (
        f"- **{d.severity}** · {d.certainty} · `{d.rule_id}`{where}: {sanitize_label(d.description)}{quote}\n"
        f"  - suggested fix: {sanitize_label(d.suggested_fix)}"
    )


def _edge_line(e: Edge, by_id: dict[str, Node]) -> str:
    s, t = by_id.get(e.source), by_id.get(e.target)
    a, b = (_code(s.label, 60) if s else "?"), (_code(t.label, 60) if t else "?")
    ev = f" — evidence: {_code(e.evidence[0].text, 100)}" if e.evidence else ""
    return f"- {a} —{e.relation}→ {b} · {e.status} · confidence {e.confidence:g} · {sanitize_label(e.rationale)}{ev}"


def to_report(doc: GraphDocument) -> str:
    by_id = {n.id: n for n in doc.nodes}
    out: list[str] = ["# PromptGraphify report", ""]
    out.append(
        f"Graph `{doc.graph_id}` · schema {doc.schema_version} · analyzer {doc.analyzer_version} · "
        f"layer B (LLM): {'on' if doc.config.layer_b else 'off'}."
    )
    out.append("")
    out.append("Built by static analysis of the text. Statuses: EXTRACTED = the text states the link explicitly; ")
    out[-1] += "INFERRED = a named rule derived it; AMBIGUOUS = more than one reading is plausible."
    out.append("")

    # --- summary
    out += ["## Summary", ""]
    out.append(f"- Files: {', '.join(_code(s.path, 80) for s in doc.sources) or 'none'}")
    types = Counter(n.type for n in doc.nodes)
    out.append(
        f"- Nodes: {len(doc.nodes)} (" + (", ".join(f"{t} {c}" for t, c in sorted(types.items())) or "none") + ")"
    )
    statuses = Counter(e.status for e in doc.edges)
    out.append(
        f"- Edges: {len(doc.edges)} (" + (", ".join(f"{s} {c}" for s, c in sorted(statuses.items())) or "none") + ")"
    )
    sev = Counter(d.severity for d in doc.diagnostics)
    out.append(
        f"- Diagnostics: {len(doc.diagnostics)} (error {sev['error']}, warning {sev['warning']}, info {sev['info']})"
    )
    out.append(f"- Execution DAG: {doc.dag.status}")
    out.append("")

    # --- most connected
    out += ["## Most connected nodes", "", f"_{DEGREE_DEFINITION}_", ""]
    deg = _degree(doc)
    order = {n.id: (n.source_file, n.source_span.start) for n in doc.nodes}
    ranked = sorted(deg, key=lambda i: (-deg[i], order.get(i, ("", 0)), i))[:TOP_N]
    if ranked:
        for i, nid in enumerate(ranked, 1):
            out.append(f"{i}. {_node(by_id[nid])} — degree {deg[nid]} — {_where(by_id[nid])}")
    else:
        out.append("No node has an edge.")
    out.append("")

    # --- execution order
    out += ["## Execution order", ""]
    dag = doc.dag
    if dag.status == "empty":
        out.append("The prompt has no ordering relations, so there is no execution order to report.")
    elif dag.status == "blocked":
        out.append(
            f"**No execution order exists: {len(dag.cycles)} dependency cycle(s) block it.** "
            "Each cycle is listed with the evidence that creates it."
        )
        out.append("")
        for i, c in enumerate(dag.cycles, 1):
            names = " → ".join(_code(by_id[v].label, 50) for v in c.nodes if v in by_id)
            out.append(f"{i}. {names} ({c.certainty})")
            for ev in c.evidence[:3]:
                out.append(f"   - evidence: {_code(ev.text, 100)}")
        if dag.removed_for_acyclic:
            out.append("")
            out.append(
                f"To get an order anyway, {len(dag.removed_for_acyclic)} dependency edge(s) would have to be removed "
                "(least certain first); nothing was removed from the graph."
            )
    else:
        for i, vid in enumerate(dag.topological_order, 1):
            if vid in by_id:
                out.append(f"{i}. {_node(by_id[vid])}")
        if dag.critical_path:
            out.append("")
            out.append(
                "Critical path: " + " → ".join(_code(by_id[v].label, 50) for v in dag.critical_path if v in by_id)
            )
        if dag.metrics:
            out.append("")
            for m in dag.metrics:
                if isinstance(m.value, dict):
                    shown = _metric_dict(m.value, by_id)
                else:
                    shown = "none" if m.value is None else str(m.value)
                out.append(f"- **{m.name}**: {shown} — _{m.definition}_")
    if dag.unresolved:
        out.append("")
        out.append("Dependencies that point at something that does not exist:")
        for u in dag.unresolved:
            n = by_id.get(u.node_id)
            out.append(f"- {_code(n.label, 60) if n else '?'} refers to {_code(u.reference, 60)}")
    out.append("")

    # --- diagnostics
    out += ["## Diagnostics", ""]
    if doc.diagnostics:
        ordered = sorted(doc.diagnostics, key=lambda d: ({"error": 0, "warning": 1, "info": 2}[d.severity], d.id))
        out += [_diag_line(d, by_id) for d in ordered]
    else:
        out.append("No diagnostics.")
    out.append("")

    # --- ambiguity for review
    out += ["## For review: ambiguous or probable", ""]
    amb = [e for e in doc.edges if e.status == "AMBIGUOUS"]
    probable = [d for d in doc.diagnostics if d.certainty == "probable"]
    if not amb and not probable:
        out.append("Nothing is ambiguous or merely probable.")
    if amb:
        out += ["AMBIGUOUS edges (the text allows more than one reading; confirm or correct):", ""]
        out += [_edge_line(e, by_id) for e in amb]
        out.append("")
    if probable:
        out.append(f"{len(probable)} finding(s) are *probable* (heuristic, not proven) — see Diagnostics above.")
    out.append("")

    # --- coverage
    out += ["## Coverage", "", "Share of the non-whitespace characters of each file that the graph accounts for.", ""]
    for c in doc.coverage:
        out.append(
            f"- {_code(c.source_file, 80)}: {c.ratio * 100:.1f}% — covered {c.covered}, structural {c.structural}, "
            f"uncovered {c.uncovered} of {c.total}"
        )
        for sp in c.uncovered_spans[:5]:
            src = next((s for s in doc.sources if s.path == c.source_file), None)
            if src is not None:
                out.append(f"  - uncovered [{sp.start}, {sp.end}): {_code(src.text[sp.start : sp.end], 100)}")
        if len(c.uncovered_spans) > 5:
            out.append(f"  - … and {len(c.uncovered_spans) - 5} more uncovered span(s)")
    out.append("")
    if doc.warnings:
        out += ["## Warnings", ""] + [f"- {sanitize_label(w)}" for w in doc.warnings] + [""]
    return "\n".join(out)


def _metric_dict(value: dict, by_id: dict[str, Node]) -> str:
    parts = []
    for k, v in value.items():
        if k == "node_id" and isinstance(v, str) and v in by_id:
            parts.append(_code(by_id[v].label, 60))
        else:
            parts.append(f"{k} {v}")
    return ", ".join(parts)
