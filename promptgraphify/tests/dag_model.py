"""A deliberately tiny, independent model of ANALYSIS_SPEC §6 used ONLY to check that the hand-written
DAG expectations in the fixtures agree with the spec. The product's DAG code (M3) is a separate
implementation and is tested against the fixtures, not against this module."""

from __future__ import annotations

import heapq

import networkx as nx

from promptgraphify.ontology import RELATION_TABLE

from .fixture_loader import Resolved


def project(res: Resolved) -> tuple[list[str], list[tuple[str, str]], list[tuple[str, str]], int]:
    """Return (vertices, arrows, ordered-loop-free arrows, loop count) per spec §6."""
    node_type = {n.key: n.type for n in res.nodes}
    arrows: list[tuple[str, str]] = []
    loops = 0
    for e in res.edges:
        mode = RELATION_TABLE[e.relation].dag
        if mode is None:
            continue
        if e.spec.get("metadata", {}).get("loop"):
            loops += 1
            continue
        a, b = (e.source, e.target) if mode == "forward" else (e.target, e.source)
        arrows.append((a, b))
    touched = {x for arrow in arrows for x in arrow}
    vertices = [n.key for n in res.nodes if node_type[n.key] == "TaskNode" or n.key in touched]
    return vertices, arrows, sorted(set(arrows)), loops


def analyse(res: Resolved) -> dict:
    vertices, _, arrows, loops = project(res)
    offset = {n.key: (n.loc.file, n.loc.span.start, n.key) for n in res.nodes}
    g = nx.DiGraph()
    g.add_nodes_from(vertices)
    g.add_edges_from(arrows)
    if not vertices:
        return {"status": "empty", "loops": loops}
    cycles = [c for c in nx.strongly_connected_components(g) if len(c) > 1 or any(g.has_edge(v, v) for v in c)]
    if cycles:
        return {"status": "blocked", "cycle_nodes": sorted(set().union(*cycles)), "loops": loops}
    indeg = dict(g.in_degree())
    ready = [(offset[v], v) for v in vertices if indeg[v] == 0]
    heapq.heapify(ready)
    order = []
    while ready:
        _, v = heapq.heappop(ready)
        order.append(v)
        for w in g.successors(v):
            indeg[w] -= 1
            if indeg[w] == 0:
                heapq.heappush(ready, (offset[w], w))
    # longest path by vertex count; ties -> lexicographically smallest offset sequence
    best: dict[str, list[str]] = {}
    for v in order:
        candidates = [best[p] for p in g.predecessors(v)]
        prefix: list[str] = []
        if candidates:
            top = max(len(c) for c in candidates)
            tied = [c for c in candidates if len(c) == top]
            prefix = min(tied, key=lambda path: [offset[x] for x in path])
        best[v] = [*prefix, v]
    longest = max(len(p) for p in best.values())
    crit = min((p for p in best.values() if len(p) == longest), key=lambda path: [offset[x] for x in path])
    return {"status": "ok", "topological_order": order, "critical_path": crit, "loops": loops}
