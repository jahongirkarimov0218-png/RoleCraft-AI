# ruff: noqa: E501
"""Execution DAG (ANALYSIS_SPEC §6): the second view of one analysis result.

Projection (u -> v means "u finishes before v starts"): PRECEDES keeps its direction, DEPENDS_ON is
reversed, CALLS_TOOL / PRODUCES / CONDITIONALLY_EXECUTES keep theirs. Loop-marked edges are excluded and
listed separately. A cycle blocks the DAG: it is reported with its edges and evidence, never dropped
silently, and a valid acyclic subgraph (with every removed edge listed) is offered next to it.
"""

from __future__ import annotations

import heapq
from dataclasses import dataclass

import networkx as nx

from .ir import CycleReport, DagEdge, DagView, Edge, Evidence, MetricValue, Node, UnresolvedDependency
from .ontology import RELATION_TABLE

STATUS_RANK = {"AMBIGUOUS": 0, "INFERRED": 1, "EXTRACTED": 2}

METRIC_DEFINITIONS = {
    "vertex_count": "Number of vertices of the execution DAG: tasks plus the tools and context values that take part in an ordering edge.",
    "arrow_count": "Number of distinct ordered pairs (u, v) in the execution DAG; several knowledge-graph edges may project to one pair.",
    "critical_path_length": (
        "Number of vertices on the longest path of the DAG (unit weight per vertex): the longest chain of "
        "prerequisites. A prompt has no time axis, so this is a dependency depth, not a duration."
    ),
    "bottleneck": (
        "Internal vertex through which the largest share of all source-to-sink paths passes (share = "
        "paths through v / all paths). Reported only if the share is greater than 0.5 (the vertex carries most paths) and the DAG is not a single chain."
    ),
    "most_prerequisites": "Vertex with the most transitive prerequisites, i.e. the most ancestors in the execution DAG.",
    "most_direct_dependencies": "Node with the most outgoing DEPENDS_ON edges in the knowledge graph (direct dependencies).",
}


@dataclass(frozen=True)
class Arrow:
    u: str
    v: str
    edge: Edge


def _order_key(n: Node) -> tuple:
    return (n.source_file, n.source_span.start, n.source_span.end, n.id)


def project(nodes: list[Node], edges: list[Edge]) -> tuple[list[str], list[Arrow], list[Edge]]:
    """(vertex ids in source order, arrows, loop edges)."""
    by_id = {n.id: n for n in nodes}
    arrows: list[Arrow] = []
    loops: list[Edge] = []
    for e in edges:
        mode = RELATION_TABLE[e.relation].dag
        if mode is None or e.source not in by_id or e.target not in by_id:
            continue
        if e.metadata.get("loop") is True:
            loops.append(e)
            continue
        u, v = (e.source, e.target) if mode == "forward" else (e.target, e.source)
        arrows.append(Arrow(u, v, e))
    touched = {a.u for a in arrows} | {a.v for a in arrows}
    vertices = sorted((n for n in nodes if n.type == "TaskNode" or n.id in touched), key=_order_key)
    return [n.id for n in vertices], arrows, loops


def _dag_edge(a: Arrow) -> DagEdge:
    cond = a.edge.relation == "CONDITIONALLY_EXECUTES"
    meta_cond = a.edge.metadata.get("condition")
    return DagEdge(
        source=a.u,
        target=a.v,
        relation=a.edge.relation,
        graph_edge=a.edge.id,
        conditional=cond,
        condition=meta_cond if isinstance(meta_cond, str) else None,
        loop=False,
    )


def _evidence_union(edges: list[Edge]) -> list[Evidence]:
    seen: set[tuple] = set()
    out: list[Evidence] = []
    for e in edges:
        for ev in e.evidence:
            key = (ev.source_file, ev.span.start, ev.span.end)
            if key not in seen:
                seen.add(key)
                out.append(ev)
    return out


def _topological(g: nx.DiGraph, key: dict[str, tuple]) -> list[str]:
    indeg = dict(g.in_degree())
    heap = [(key[v], v) for v in g if indeg[v] == 0]
    heapq.heapify(heap)
    order: list[str] = []
    while heap:
        _, v = heapq.heappop(heap)
        order.append(v)
        for w in g.successors(v):
            indeg[w] -= 1
            if indeg[w] == 0:
                heapq.heappush(heap, (key[w], w))
    return order


def _critical_path(g: nx.DiGraph, order: list[str], key: dict[str, tuple]) -> list[str]:
    best: dict[str, list[str]] = {}
    for v in order:
        preds = [best[p] for p in g.predecessors(v)]
        prefix: list[str] = []
        if preds:
            top = max(len(p) for p in preds)
            prefix = min((p for p in preds if len(p) == top), key=lambda path: [key[x] for x in path])
        best[v] = [*prefix, v]
    if not best:
        return []
    longest = max(len(p) for p in best.values())
    return min((p for p in best.values() if len(p) == longest), key=lambda path: [key[x] for x in path])


def _break_cycles(arrows: list[Arrow], key: dict[str, tuple]) -> tuple[list[Arrow], list[Edge]]:
    """Remove one arrow at a time, always from a cycle, preferring the least certain edge (ambiguous <
    inferred < extracted, then lower confidence, then the one whose source comes last in the text), until
    the rest is acyclic. Returns (kept arrows, removed graph edges)."""
    kept = list(arrows)
    removed: list[Edge] = []
    while True:
        g = nx.DiGraph()
        g.add_edges_from((a.u, a.v) for a in kept)
        try:
            cycle = nx.find_cycle(g)
        except nx.NetworkXNoCycle:
            return kept, removed
        pairs = {(u, v) for u, v in cycle}
        candidates = [a for a in kept if (a.u, a.v) in pairs]
        victim = min(candidates, key=lambda a: (STATUS_RANK[a.edge.status], a.edge.confidence, -key[a.u][1], a.edge.id))
        # drop every arrow that projects to the same ordered pair as the victim: one logical dependency
        same = [a for a in kept if (a.u, a.v) == (victim.u, victim.v)]
        for a in same:
            kept.remove(a)
            removed.append(a.edge)


def _metrics(
    g: nx.DiGraph, order: list[str], path: list[str], key: dict[str, tuple], edges: list[Edge]
) -> list[MetricValue]:
    out = [
        MetricValue(name="vertex_count", value=g.number_of_nodes(), definition=METRIC_DEFINITIONS["vertex_count"]),
        MetricValue(name="arrow_count", value=g.number_of_edges(), definition=METRIC_DEFINITIONS["arrow_count"]),
        MetricValue(
            name="critical_path_length", value=len(path), definition=METRIC_DEFINITIONS["critical_path_length"]
        ),
    ]
    if order:
        # path counts: from sources to v and from v to sinks
        to_v: dict[str, int] = {}
        for v in order:
            preds = list(g.predecessors(v))
            to_v[v] = 1 if not preds else sum(to_v[p] for p in preds)
        from_v: dict[str, int] = {}
        for v in reversed(order):
            succ = list(g.successors(v))
            from_v[v] = 1 if not succ else sum(from_v[s] for s in succ)
        total = sum(to_v[v] for v in order if g.out_degree(v) == 0)
        single_chain = (
            all(g.in_degree(v) <= 1 and g.out_degree(v) <= 1 for v in g)
            and nx.number_weakly_connected_components(g) == 1
        )
        best = None
        if total and g.number_of_nodes() >= 3 and not single_chain:
            internal = [v for v in order if g.in_degree(v) > 0 and g.out_degree(v) > 0]
            if internal:
                top = max(to_v[x] * from_v[x] for x in internal)
                tied = [x for x in internal if to_v[x] * from_v[x] == top]
                v = min(tied, key=lambda x: key[x])
                share = top / total
                if share > 0.5:
                    best = {"node_id": v, "share": round(share, 4)}
        out.append(MetricValue(name="bottleneck", value=best, definition=METRIC_DEFINITIONS["bottleneck"]))
        anc = {v: len(nx.ancestors(g, v)) for v in g}
        if anc:
            top = max(anc.values())
            v = min((x for x in anc if anc[x] == top), key=lambda x: key[x])
            out.append(
                MetricValue(
                    name="most_prerequisites",
                    value={"node_id": v, "count": top},
                    definition=METRIC_DEFINITIONS["most_prerequisites"],
                )
            )
    direct: dict[str, int] = {}
    for e in edges:
        if e.relation == "DEPENDS_ON" and e.source != e.target:
            direct[e.source] = direct.get(e.source, 0) + 1
    if direct:
        top = max(direct.values())
        v = min((x for x in direct if direct[x] == top), key=lambda x: key.get(x, (chr(0x10FFFF), 0, 0, x)))
        out.append(
            MetricValue(
                name="most_direct_dependencies",
                value={"node_id": v, "count": top},
                definition=METRIC_DEFINITIONS["most_direct_dependencies"],
            )
        )
    return out


def build_dag(nodes: list[Node], edges: list[Edge], unresolved: list[UnresolvedDependency]) -> DagView:
    vertices, arrows, loop_edges = project(nodes, edges)
    by_id = {n.id: n for n in nodes}
    key = {nid: _order_key(by_id[nid]) for nid in vertices}
    loops = sorted(e.id for e in loop_edges)
    if not vertices:
        return DagView(
            status="empty", vertices=[], edges=[], topological_order=[], critical_path=[], unresolved=unresolved,
            cycles=[], acyclic_subgraph=None, removed_for_acyclic=[], loops=loops, metrics=[],
        )  # fmt: skip
    g = nx.DiGraph()
    g.add_nodes_from(vertices)
    g.add_edges_from((a.u, a.v) for a in arrows)
    dag_edges = [_dag_edge(a) for a in sorted(arrows, key=lambda a: (key[a.u], key[a.v], a.edge.id))]

    cyclic = [c for c in nx.strongly_connected_components(g) if len(c) > 1 or any(g.has_edge(v, v) for v in c)]
    if not cyclic:
        order = _topological(g, key)
        path = _critical_path(g, order, key)
        return DagView(
            status="ok", vertices=vertices, edges=dag_edges, topological_order=order, critical_path=path,
            unresolved=unresolved, cycles=[], acyclic_subgraph=None, removed_for_acyclic=[], loops=loops,
            metrics=_metrics(g, order, path, key, edges),
        )  # fmt: skip

    reports: list[CycleReport] = []
    for comp in sorted(cyclic, key=lambda c: min(key[v] for v in c)):
        inside = [a for a in arrows if a.u in comp and a.v in comp]
        involved = [a.edge for a in inside]
        certainty = "proven" if all(e.status == "EXTRACTED" for e in involved) else "probable"
        reports.append(
            CycleReport(
                nodes=sorted(comp, key=lambda v: key[v]),
                edges=sorted({e.id for e in involved}),
                evidence=_evidence_union(sorted(involved, key=lambda e: e.id)),
                certainty=certainty,
            )
        )
    kept, removed = _break_cycles(arrows, key)
    subgraph = [_dag_edge(a) for a in sorted(kept, key=lambda a: (key[a.u], key[a.v], a.edge.id))]
    return DagView(
        status="blocked", vertices=vertices, edges=dag_edges, topological_order=[], critical_path=[],
        unresolved=unresolved, cycles=reports, acyclic_subgraph=subgraph,
        removed_for_acyclic=sorted({e.id for e in removed}), loops=loops, metrics=[],
    )  # fmt: skip


def unschedulable(nodes: list[Node], edges: list[Edge], unresolved: list[UnresolvedDependency]) -> set[str]:
    """Vertices Kahn's algorithm never emits (on or after a cycle) plus tasks with a missing dependency."""
    vertices, arrows, _ = project(nodes, edges)
    by_id = {n.id: n for n in nodes}
    key = {nid: _order_key(by_id[nid]) for nid in vertices}
    g = nx.DiGraph()
    g.add_nodes_from(vertices)
    g.add_edges_from((a.u, a.v) for a in arrows)
    emitted = set(_topological(g, key))
    blocked = set(vertices) - emitted
    blocked |= {u.node_id for u in unresolved}
    for b in list(blocked):
        if b in g:
            blocked |= nx.descendants(g, b)
    return blocked
