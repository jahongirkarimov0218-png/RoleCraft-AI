// Pure helpers that derive what the UI shows from a GraphDocument. No data of its own: every node and
// edge on screen comes from the analysis result.

import { graphlib, layout } from "@dagrejs/dagre";
import type { EdgeStatus, GraphDocument, GraphEdge, GraphNode, NodeType } from "./types";

export const NODE_W = 200;
export const NODE_H = 64;

export const TYPE_COLOR: Record<NodeType, string> = {
  SystemNode: "var(--c-system)",
  TaskNode: "var(--c-task)",
  ContextNode: "var(--c-context)",
  ConstraintNode: "var(--c-constraint)",
  ToolNode: "var(--c-tool)",
  ExampleNode: "var(--c-example)",
};

export const TYPE_LABEL: Record<NodeType, string> = {
  SystemNode: "System",
  TaskNode: "Task",
  ContextNode: "Context",
  ConstraintNode: "Constraint",
  ToolNode: "Tool",
  ExampleNode: "Example",
};

export const STATUS_DASH: Record<EdgeStatus, string | undefined> = {
  EXTRACTED: undefined,
  INFERRED: "6 4",
  AMBIGUOUS: "2 4",
};

export interface Filters {
  types: Set<NodeType>;
  statuses: Set<EdgeStatus>;
  search: string;
}

export function matchesSearch(node: GraphNode, query: string): boolean {
  const q = query.trim().toLowerCase();
  if (!q) return true;
  return (
    node.label.toLowerCase().includes(q) ||
    node.original_text.toLowerCase().includes(q) ||
    node.id.toLowerCase().includes(q) ||
    node.type.toLowerCase().includes(q)
  );
}

export function visibleIds(doc: GraphDocument, filters: Filters): { nodes: Set<string>; edges: Set<string> } {
  const nodes = new Set(doc.nodes.filter((n) => filters.types.has(n.type)).map((n) => n.id));
  const edges = new Set(
    doc.edges.filter((e) => filters.statuses.has(e.status) && nodes.has(e.source) && nodes.has(e.target)).map((e) => e.id),
  );
  return { nodes, edges };
}

/** Selected element plus everything directly connected to it. */
export function neighborhood(doc: GraphDocument, sel: { kind: "node" | "edge"; id: string } | null) {
  const nodes = new Set<string>();
  const edges = new Set<string>();
  if (!sel) return { nodes, edges };
  if (sel.kind === "node") {
    nodes.add(sel.id);
    for (const e of doc.edges) {
      if (e.source === sel.id || e.target === sel.id) {
        edges.add(e.id);
        nodes.add(e.source);
        nodes.add(e.target);
      }
    }
  } else {
    const e = doc.edges.find((x) => x.id === sel.id);
    if (e) {
      edges.add(e.id);
      nodes.add(e.source);
      nodes.add(e.target);
    }
  }
  return { nodes, edges };
}

export type Positions = Map<string, { x: number; y: number }>;

/** Layered left-to-right layout (dagre). Cycles are tolerated: dagre breaks them internally for ranking
 *  only; every edge is still drawn. */
export function computeLayout(
  nodeIds: string[],
  edges: { source: string; target: string }[],
  direction: "LR" | "TB" = "LR",
): Positions {
  const g = new graphlib.Graph({ multigraph: false });
  g.setGraph({ rankdir: direction, nodesep: 28, ranksep: 56, marginx: 24, marginy: 24 });
  g.setDefaultEdgeLabel(() => ({}));
  for (const id of nodeIds) g.setNode(id, { width: NODE_W, height: NODE_H });
  const seen = new Set<string>();
  for (const e of edges) {
    if (e.source === e.target) continue;
    const key = `${e.source}\u0000${e.target}`;
    if (seen.has(key)) continue;
    seen.add(key);
    g.setEdge(e.source, e.target);
  }
  layout(g);
  const out: Positions = new Map();
  for (const id of nodeIds) {
    const n = g.node(id);
    out.set(id, { x: n.x - NODE_W / 2, y: n.y - NODE_H / 2 });
  }
  return out;
}

/** Index of parallel edges (same ordered pair) so they can be drawn with different curvature. */
export function parallelIndex(edges: GraphEdge[]): Map<string, { index: number; total: number }> {
  const groups = new Map<string, string[]>();
  for (const e of edges) {
    const key = [e.source, e.target].sort().join("\u0000");
    groups.set(key, [...(groups.get(key) ?? []), e.id]);
  }
  const out = new Map<string, { index: number; total: number }>();
  for (const ids of groups.values()) ids.forEach((id, index) => out.set(id, { index, total: ids.length }));
  return out;
}

/** Smallest node whose span contains the given code point offset (used for editor -> graph selection). */
export function nodeAtOffset(doc: GraphDocument, file: string, cp: number): GraphNode | null {
  let best: GraphNode | null = null;
  for (const n of doc.nodes) {
    if (n.source_file !== file) continue;
    const { start, end } = n.source_span;
    if (cp >= start && cp <= end && (!best || end - start < best.source_span.end - best.source_span.start)) best = n;
  }
  return best;
}
