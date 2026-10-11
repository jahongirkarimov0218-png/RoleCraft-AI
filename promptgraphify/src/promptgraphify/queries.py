"""Named, parameterised, deterministic queries over a GraphDocument (CLI, API and UI all call this).

Every answer is built from graph facts only and carries source evidence; there is no free-text
understanding and no LLM. A name that matches several nodes is never guessed: the candidates are
returned with ``status = "ambiguous"``.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Literal

import networkx as nx
from pydantic import BaseModel, ConfigDict, Field

from .ir import Edge, Evidence, GraphDocument, Node
from .spans import Span

Status = Literal["ok", "ambiguous", "not_found", "no_path", "invalid"]
Basis = Literal["explicit", "inferred", "mixed", "structural"]


class _M(BaseModel):
    model_config = ConfigDict(extra="forbid")


class NodeRef(_M):
    id: str
    type: str
    label: str
    source_file: str
    span: Span
    original_text: str


class EdgeRef(_M):
    id: str
    relation: str
    status: str
    source: str
    target: str
    rationale: str


class Row(_M):
    title: str
    detail: str
    basis: Basis
    node_ids: list[str]
    edge_ids: list[str]
    evidence: list[Evidence]


class ParamSpec(_M):
    name: str
    description: str
    required: bool


class QuerySpec(_M):
    name: str
    title: str
    question: str
    definition: str
    params: list[ParamSpec]


class QueryResult(_M):
    query: str
    params: dict[str, str]
    status: Status
    summary: str
    rows: list[Row]
    nodes: list[NodeRef]
    edges: list[EdgeRef]
    paths: list[list[str]]
    candidates: list[NodeRef]


QUERY_SPECS: list[QuerySpec] = [
    QuerySpec(
        name="task_context",
        title="Context a task depends on",
        question="Which ContextNodes does this TaskNode depend on?",
        definition="Context nodes reached by an outgoing DEPENDS_ON edge of the task, plus context blocks that PROVIDE_CONTEXT to it.",
        params=[ParamSpec(name="task", description="Task label, id or a unique part of its text", required=True)],
    ),
    QuerySpec(
        name="constraints_on_tasks",
        title="Constraints per task",
        question="Which constraints affect which tasks?",
        definition="CONSTRAINS edges from ConstraintNodes to TaskNodes. Global constraints (outside any section) are listed with every task of their agent/file and marked as inferred.",
        params=[ParamSpec(name="task", description="Optional: only constraints affecting this task", required=False)],
    ),
    QuerySpec(
        name="agent_tools",
        title="Tools per agent",
        question="Which agent uses which tool?",
        definition="CALLS_TOOL edges grouped by the agent (role_scope.agent) of the calling task; tasks without an agent are grouped under '(no agent)'.",
        params=[],
    ),
    QuerySpec(
        name="unused_variables",
        title="Declared but unused variables",
        question="Which variables are declared but never used?",
        definition="ContextNodes with metadata.declared = true and no recorded usage.",
        params=[],
    ),
    QuerySpec(
        name="shortest_path",
        title="Shortest path between two nodes",
        question="What is the shortest path between two nodes?",
        definition="Fewest edges following the stored edge direction (use undirected=true to ignore direction). Ties are broken by edge id so the answer is stable.",
        params=[
            ParamSpec(name="source", description="Label, id or unique text of the start node", required=True),
            ParamSpec(name="target", description="Label, id or unique text of the end node", required=True),
            ParamSpec(name="undirected", description="'true' to ignore edge direction", required=False),
        ],
    ),
    QuerySpec(
        name="execution_bottleneck",
        title="Execution bottleneck",
        question="Where is the execution bottleneck?",
        definition="The internal vertex of the execution DAG that carries more than half of all source-to-sink paths (see dag.metrics); also shows the critical path (longest chain of prerequisites).",
        params=[],
    ),
    QuerySpec(
        name="conflicts",
        title="Conflicting instructions",
        question="Which instruction contradicts another?",
        definition="CONFLICTS_WITH edges (always inferred: a conflict is a judgement, not an explicit reference).",
        params=[],
    ),
    QuerySpec(
        name="most_dependent",
        title="Parts with the most dependencies",
        question="Which parts of the prompt have the most dependencies?",
        definition="Ranked by transitive prerequisites (ancestors in the execution DAG), then by direct dependencies (outgoing DEPENDS_ON edges), then by source order.",
        params=[ParamSpec(name="top", description="How many to list (default 5)", required=False)],
    ),
]
QUERY_NAMES = [q.name for q in QUERY_SPECS]


# ------------------------------------------------------------------------------------------ resolution
class _Ctx:
    def __init__(self, doc: GraphDocument):
        self.doc = doc
        self.nodes = {n.id: n for n in doc.nodes}
        self.edges = {e.id: e for e in doc.edges}
        self.used_nodes: dict[str, Node] = {}
        self.used_edges: dict[str, Edge] = {}

    def node(self, nid: str) -> Node:
        n = self.nodes[nid]
        self.used_nodes[nid] = n
        return n

    def edge(self, eid: str) -> Edge:
        e = self.edges[eid]
        self.used_edges[eid] = e
        self.node(e.source)
        self.node(e.target)
        return e


def node_ref(n: Node) -> NodeRef:
    return NodeRef(
        id=n.id,
        type=n.type,
        label=n.label,
        source_file=n.source_file,
        span=n.source_span,
        original_text=n.original_text,
    )


def _edge_ref(e: Edge) -> EdgeRef:
    return EdgeRef(
        id=e.id, relation=e.relation, status=e.status, source=e.source, target=e.target, rationale=e.rationale
    )


def resolve(doc: GraphDocument, text: str, types: tuple[str, ...] | None = None) -> list[Node]:
    """All nodes matching ``text`` at the best tier: id, exact label, exact text, then substring."""
    pool = [n for n in doc.nodes if types is None or n.type in types]
    q = text.strip()
    ql = q.lower()
    if not q:
        return []
    for tier in (
        lambda n: n.id == q,
        lambda n: n.label.lower() == ql,
        lambda n: (n.decoded_text or n.original_text).strip().lower() == ql,
        lambda n: ql in n.label.lower() or ql in n.original_text.lower() or ql in n.id.lower(),
    ):
        hits = [n for n in pool if tier(n)]
        if hits:
            return hits
    return []


def _basis(edges: list[Edge]) -> Basis:
    if not edges:
        return "structural"
    statuses = {e.status for e in edges}
    return "explicit" if statuses == {"EXTRACTED"} else "inferred" if "EXTRACTED" not in statuses else "mixed"


def _ev_node(n: Node) -> Evidence:
    return Evidence(source_file=n.source_file, span=n.source_span, text=n.original_text)


def _row(
    ctx: _Ctx, title: str, detail: str, nodes: list[str], edges: list[str], *, evidence_from_nodes: bool = True
) -> Row:
    es = [ctx.edge(e) for e in edges]
    ns = [ctx.node(n) for n in nodes]
    evidence: list[Evidence] = []
    seen: set[tuple] = set()
    for e in es:
        for ev in e.evidence:
            k = (ev.source_file, ev.span.start, ev.span.end)
            if k not in seen:
                seen.add(k)
                evidence.append(ev)
    if not evidence and evidence_from_nodes:
        evidence = [_ev_node(n) for n in ns]
    return Row(title=title, detail=detail, basis=_basis(es), node_ids=nodes, edge_ids=edges, evidence=evidence)


def _result(
    ctx: _Ctx,
    query: str,
    params: dict[str, str],
    status: Status,
    summary: str,
    rows: list[Row],
    paths: list[list[str]] | None = None,
    candidates: list[Node] | None = None,
) -> QueryResult:
    return QueryResult(
        query=query,
        params=params,
        status=status,
        summary=summary,
        rows=rows,
        nodes=[node_ref(n) for _, n in sorted(ctx.used_nodes.items())],
        edges=[_edge_ref(e) for _, e in sorted(ctx.used_edges.items())],
        paths=paths or [],
        candidates=[node_ref(n) for n in candidates or []],
    )


def _pick(
    ctx: _Ctx, query: str, params: dict[str, str], name: str, types: tuple[str, ...], label: str
) -> Node | QueryResult:
    hits = resolve(ctx.doc, params.get(name, ""), types or None)
    if not hits:
        return _result(ctx, query, params, "not_found", f"No {label} matches {params.get(name, '')!r}.", [])
    if len(hits) > 1:
        return _result(
            ctx,
            query,
            params,
            "ambiguous",
            f"{params[name]!r} matches {len(hits)} nodes; give a more specific name or an id.",
            [],
            candidates=hits,
        )
    return hits[0]


# -------------------------------------------------------------------------------------------- queries
def q_task_context(ctx: _Ctx, params: dict[str, str]) -> QueryResult:
    task = _pick(ctx, "task_context", params, "task", ("TaskNode",), "task")
    if isinstance(task, QueryResult):
        return task
    ctx.node(task.id)
    rows = []
    for e in sorted(ctx.doc.edges, key=lambda x: x.id):
        other = None
        if e.relation == "DEPENDS_ON" and e.source == task.id and ctx.nodes[e.target].type == "ContextNode":
            other, verb = ctx.nodes[e.target], "depends on"
        elif e.relation == "PROVIDES_CONTEXT" and e.target == task.id and ctx.nodes[e.source].type == "ContextNode":
            other, verb = ctx.nodes[e.source], "is given context by"
        if other is not None:
            rows.append(
                _row(
                    ctx,
                    other.label,
                    f"The task {verb} {other.label} ({e.status.lower()}: {e.rationale})",
                    [other.id],
                    [e.id],
                )
            )
    summary = (
        f"{task.label!r} relies on {len(rows)} context node(s)."
        if rows
        else f"{task.label!r} has no recorded dependency on a context node."
    )
    return _result(ctx, "task_context", params, "ok", summary, rows)


def q_constraints_on_tasks(ctx: _Ctx, params: dict[str, str]) -> QueryResult:
    focus: Node | None = None
    if params.get("task"):
        picked = _pick(ctx, "constraints_on_tasks", params, "task", ("TaskNode",), "task")
        if isinstance(picked, QueryResult):
            return picked
        focus = picked
    tasks = [n for n in ctx.doc.nodes if n.type == "TaskNode" and (focus is None or n.id == focus.id)]
    rows = []
    for c in (n for n in ctx.doc.nodes if n.type == "ConstraintNode"):
        edges = [
            e
            for e in ctx.doc.edges
            if e.relation == "CONSTRAINS" and e.source == c.id and ctx.nodes[e.target].type == "TaskNode"
        ]
        hit = [e for e in edges if focus is None or e.target == focus.id]
        affected = [e.target for e in hit]
        detail = f"{len(affected)} task(s) in section {c.metadata.get('scope')!r}"
        if c.metadata.get("scope") == "global":
            same = [t.id for t in tasks if t.source_file == c.source_file and t.role_scope.agent == c.role_scope.agent]
            affected = sorted(set(affected) | set(same))
            detail = f"global scope: applies to all {len(affected)} task(s) of this file/agent (inferred, not an edge)"
        if affected:
            rows.append(_row(ctx, c.label, detail, [c.id, *affected], [e.id for e in hit]))
    summary = (
        f"{len(rows)} constraint(s) affect {'the task ' + repr(focus.label) if focus else 'tasks'}."
        if rows
        else "No constraint affects a task."
    )
    return _result(ctx, "constraints_on_tasks", params, "ok", summary, rows)


def q_agent_tools(ctx: _Ctx, params: dict[str, str]) -> QueryResult:
    by_agent: dict[str, list[Edge]] = {}
    for e in sorted(ctx.doc.edges, key=lambda x: x.id):
        if e.relation == "CALLS_TOOL":
            by_agent.setdefault(ctx.nodes[e.source].role_scope.agent or "(no agent)", []).append(e)
    rows = []
    for agent in sorted(by_agent):
        es = by_agent[agent]
        tools = sorted({ctx.nodes[e.target].label for e in es})
        undefined = sorted(
            {ctx.nodes[e.target].label for e in es if ctx.nodes[e.target].metadata.get("defined") is False}
        )
        extra = f"; undefined: {', '.join(undefined)}" if undefined else ""
        rows.append(
            _row(
                ctx,
                agent,
                f"uses {', '.join(tools)}{extra}",
                sorted({n for e in es for n in (e.source, e.target)}),
                [e.id for e in es],
            )
        )
    summary = f"{len(rows)} agent(s) call tools." if rows else "No task calls a tool."
    return _result(ctx, "agent_tools", params, "ok", summary, rows)


def q_unused_variables(ctx: _Ctx, params: dict[str, str]) -> QueryResult:
    rows = [
        _row(ctx, n.label, f"{n.label} is declared but never used", [n.id], [])
        for n in ctx.doc.nodes
        if n.type == "ContextNode" and n.metadata.get("declared") is True and not n.metadata.get("usage_spans")
    ]
    return _result(ctx, "unused_variables", params, "ok", f"{len(rows)} declared variable(s) are never used.", rows)


def q_shortest_path(ctx: _Ctx, params: dict[str, str]) -> QueryResult:
    src = _pick(ctx, "shortest_path", params, "source", (), "source node")
    if isinstance(src, QueryResult):
        return src
    tgt = _pick(ctx, "shortest_path", params, "target", (), "target node")
    if isinstance(tgt, QueryResult):
        return tgt
    if src.id == tgt.id:
        return _result(ctx, "shortest_path", params, "invalid", "Source and target are the same node.", [])
    undirected = params.get("undirected", "").lower() == "true"
    g = nx.MultiDiGraph()
    g.add_nodes_from(sorted(ctx.nodes))
    for e in sorted(ctx.doc.edges, key=lambda x: x.id):
        g.add_edge(e.source, e.target, key=e.id)
        if undirected:
            g.add_edge(e.target, e.source, key=e.id)
    try:
        path = nx.shortest_path(nx.DiGraph(g), src.id, tgt.id)
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        hint = "" if undirected else " Retry with undirected=true to ignore edge direction."
        ctx.node(src.id), ctx.node(tgt.id)
        return _result(
            ctx,
            "shortest_path",
            params,
            "no_path",
            f"No {'path' if undirected else 'directed path'} from {src.label!r} to {tgt.label!r}.{hint}",
            [],
        )
    rows = []
    for a, b in zip(path, path[1:], strict=False):
        keys = sorted(k for k in g[a][b])
        e = ctx.edges[keys[0]]
        direction = "→" if (e.source, e.target) == (a, b) else "←"
        rows.append(
            _row(
                ctx,
                f"{ctx.nodes[a].label} {direction} {ctx.nodes[b].label}",
                f"{e.relation} ({e.status.lower()}): {e.rationale}",
                [a, b],
                [e.id],
            )
        )
    for n in path:
        ctx.node(n)
    return _result(
        ctx,
        "shortest_path",
        params,
        "ok",
        f"{len(path) - 1} hop(s) from {src.label!r} to {tgt.label!r}.",
        rows,
        paths=[path],
    )


def q_execution_bottleneck(ctx: _Ctx, params: dict[str, str]) -> QueryResult:
    dag = ctx.doc.dag
    if dag.status != "ok":
        reason = "the execution DAG is blocked by a cycle" if dag.status == "blocked" else "there are no tasks"
        return _result(ctx, "execution_bottleneck", params, "ok", f"No bottleneck: {reason}.", [])
    rows = []
    metrics = {m.name: m for m in dag.metrics}
    b = metrics.get("bottleneck")
    if b and b.value:
        v = b.value  # type: ignore[assignment]
        n = ctx.node(v["node_id"])  # type: ignore[index]
        rows.append(
            _row(
                ctx,
                n.label,
                f"{v['share']:.0%} of all source-to-sink paths pass through this vertex. {b.definition}",
                [n.id],
                [],
            )
        )  # type: ignore[index]
    path = dag.critical_path
    if path:
        rows.append(
            _row(
                ctx,
                "critical path",
                f"longest chain of prerequisites: {len(path)} vertices. {metrics['critical_path_length'].definition}",
                path,
                [],
                evidence_from_nodes=True,
            )
        )
    summary = (
        "One vertex carries most execution paths."
        if b and b.value
        else "No single vertex carries most execution paths."
    )
    return _result(ctx, "execution_bottleneck", params, "ok", summary, rows, paths=[path] if path else [])


def q_conflicts(ctx: _Ctx, params: dict[str, str]) -> QueryResult:
    rows = []
    for e in sorted(ctx.doc.edges, key=lambda x: x.id):
        if e.relation == "CONFLICTS_WITH":
            a, b = ctx.nodes[e.source], ctx.nodes[e.target]
            rows.append(
                _row(
                    ctx,
                    f"{a.label} ⟷ {b.label}",
                    f"probable conflict ({e.status.lower()}): {e.rationale}",
                    [a.id, b.id],
                    [e.id],
                )
            )
    return _result(ctx, "conflicts", params, "ok", f"{len(rows)} probable conflict(s).", rows)


def q_most_dependent(ctx: _Ctx, params: dict[str, str]) -> QueryResult:
    try:
        top = max(1, int(params.get("top", "5")))
    except ValueError:
        return _result(ctx, "most_dependent", params, "invalid", "top must be a whole number.", [])
    g = nx.DiGraph()
    g.add_nodes_from(ctx.doc.dag.vertices)
    g.add_edges_from((e.source, e.target) for e in ctx.doc.dag.edges)
    direct: dict[str, list[Edge]] = {}
    for e in ctx.doc.edges:
        if e.relation == "DEPENDS_ON" and e.source != e.target:
            direct.setdefault(e.source, []).append(e)
    order = {n.id: (n.source_file, n.source_span.start) for n in ctx.doc.nodes}
    scored = []
    for nid in ctx.nodes:
        trans = len(nx.ancestors(g, nid)) if nid in g else 0
        d = len(direct.get(nid, []))
        if trans or d:
            scored.append((-trans, -d, order[nid], nid, trans, d))
    scored.sort()
    rows = []
    for *_, nid, trans, d in scored[:top]:
        n = ctx.node(nid)
        rows.append(
            _row(
                ctx,
                n.label,
                f"{trans} transitive prerequisite(s), {d} direct dependency(ies)",
                [nid],
                [e.id for e in direct.get(nid, [])],
            )
        )
    return _result(ctx, "most_dependent", params, "ok", f"Top {len(rows)} part(s) by dependencies.", rows)


QUERY_FUNCTIONS: dict[str, Callable[[_Ctx, dict[str, str]], QueryResult]] = {
    "task_context": q_task_context,
    "constraints_on_tasks": q_constraints_on_tasks,
    "agent_tools": q_agent_tools,
    "unused_variables": q_unused_variables,
    "shortest_path": q_shortest_path,
    "execution_bottleneck": q_execution_bottleneck,
    "conflicts": q_conflicts,
    "most_dependent": q_most_dependent,
}


def run_query(doc: GraphDocument, name: str, params: dict[str, str] | None = None) -> QueryResult:
    params = {k: str(v) for k, v in (params or {}).items()}
    spec = next((q for q in QUERY_SPECS if q.name == name), None)
    ctx = _Ctx(doc)
    if spec is None:
        return _result(ctx, name, params, "invalid", f"Unknown query {name!r}. Known: {', '.join(QUERY_NAMES)}.", [])
    missing = [p.name for p in spec.params if p.required and not params.get(p.name)]
    if missing:
        return _result(ctx, name, params, "invalid", f"Missing required parameter(s): {', '.join(missing)}.", [])
    return QUERY_FUNCTIONS[name](ctx, params)


def explain_node(doc: GraphDocument, name: str) -> QueryResult:
    """CLI `explain`: one node with everything connected to it, evidence included."""
    ctx = _Ctx(doc)
    picked = _pick(ctx, "explain", {"name": name}, "name", (), "node")
    if isinstance(picked, QueryResult):
        return picked
    n = ctx.node(picked.id)
    rows = [
        _row(
            ctx,
            f"{n.type} {n.label}",
            f"{n.description}; span [{n.source_span.start}, {n.source_span.end}) in {n.source_file}",
            [n.id],
            [],
        )
    ]
    for e in sorted(doc.edges, key=lambda x: (x.relation, x.id)):
        if n.id in (e.source, e.target):
            other = ctx.nodes[e.target if e.source == n.id else e.source]
            way = "→" if e.source == n.id else "←"
            rows.append(
                _row(
                    ctx,
                    f"{e.relation} {way} {other.label}",
                    f"{e.status.lower()}: {e.rationale}",
                    [n.id, other.id],
                    [e.id],
                )
            )
    return _result(ctx, "explain", {"name": name}, "ok", f"{n.type} {n.label!r}: {len(rows) - 1} relation(s).", rows)
