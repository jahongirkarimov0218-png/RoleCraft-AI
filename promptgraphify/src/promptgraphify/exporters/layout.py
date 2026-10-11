"""A small deterministic layered layout used by the SVG and HTML exports (no external layout engine).

Ranks come from longest-path layering on the condensation (strongly connected components share a rank
band), vertices inside a rank are ordered by their position in the source text.
"""

from __future__ import annotations

import networkx as nx

NODE_W = 200
NODE_H = 56
GAP_X = 90
GAP_Y = 26
MARGIN = 24


def layered_layout(
    ids: list[str], edges: list[tuple[str, str]], order: dict[str, tuple]
) -> tuple[dict[str, tuple[float, float]], float, float]:
    g = nx.DiGraph()
    g.add_nodes_from(ids)
    g.add_edges_from((a, b) for a, b in edges if a != b and a in g and b in g)
    cond = nx.condensation(g)
    rank_of_comp: dict[int, int] = {}
    for comp in nx.topological_sort(cond):
        preds = list(cond.predecessors(comp))
        rank_of_comp[comp] = 1 + max(rank_of_comp[p] for p in preds) if preds else 0
    rank = {n: rank_of_comp[cond.graph["mapping"][n]] for n in g}
    by_rank: dict[int, list[str]] = {}
    for n in sorted(g, key=lambda x: order.get(x, ("", 0, x))):
        by_rank.setdefault(rank[n], []).append(n)
    pos: dict[str, tuple[float, float]] = {}
    for r, members in by_rank.items():
        for i, n in enumerate(members):
            pos[n] = (MARGIN + r * (NODE_W + GAP_X), MARGIN + i * (NODE_H + GAP_Y))
    width = MARGIN * 2 + (max(by_rank) + 1) * (NODE_W + GAP_X) - GAP_X if by_rank else MARGIN * 2
    height = (
        MARGIN * 2 + max((len(m) for m in by_rank.values()), default=0) * (NODE_H + GAP_Y) - GAP_Y
        if by_rank
        else MARGIN * 2
    )
    return pos, float(max(width, 2 * MARGIN)), float(max(height, 2 * MARGIN))
