import { describe, expect, it } from "vitest";
import { computeLayout, matchesSearch, neighborhood, nodeAtOffset, parallelIndex, visibleIds } from "@/lib/graph-view";
import type { GraphDocument, GraphEdge, GraphNode } from "@/lib/types";
import { EDGE_STATUSES, NODE_TYPES } from "@/lib/types";

// Tiny hand-built documents: these helpers test pure view logic, not analysis.
const node = (id: string, type: GraphNode["type"], start: number, end: number, text = id): GraphNode =>
  ({
    id, type, label: text, description: "", original_text: text, decoded_text: null, source_file: "p.md",
    source_span: { start, end }, role_scope: { role: null, agent: null }, metadata: {}, extraction_method: "deterministic:t",
    confidence: 1, validation_status: "verified",
  }) as GraphNode;
const edge = (id: string, s: string, t: string, status: GraphEdge["status"] = "EXTRACTED"): GraphEdge =>
  ({
    id, source: s, target: t, relation: "DEPENDS_ON", rationale: "", evidence: [], status, reference: "x", rule: null,
    extraction_method: "deterministic:t", metadata: {}, confidence: 1,
  }) as GraphEdge;
const doc = (nodes: GraphNode[], edges: GraphEdge[]) => ({ graph_id: "g", nodes, edges }) as unknown as GraphDocument;
const filters = (over: Partial<{ types: Set<GraphNode["type"]>; statuses: Set<GraphEdge["status"]>; search: string }> = {}) => ({
  types: new Set(NODE_TYPES), statuses: new Set(EDGE_STATUSES), search: "", ...over,
});

const D = doc(
  [node("a", "TaskNode", 0, 10), node("b", "ContextNode", 20, 30), node("c", "ConstraintNode", 40, 60), node("d", "ToolNode", 70, 80)],
  [edge("e1", "a", "b"), edge("e2", "c", "a", "INFERRED"), edge("e3", "a", "b", "AMBIGUOUS")],
);

describe("graph view helpers", () => {
  it("filters nodes by type and drops edges whose endpoint is hidden", () => {
    const v = visibleIds(D, filters({ types: new Set(["TaskNode", "ContextNode"]) }));
    expect([...v.nodes].sort()).toEqual(["a", "b"]);
    expect([...v.edges].sort()).toEqual(["e1", "e3"]);
  });

  it("filters edges by status", () => {
    const v = visibleIds(D, filters({ statuses: new Set(["INFERRED"]) }));
    expect([...v.edges]).toEqual(["e2"]);
  });

  it("neighborhood of a node is the node, its edges and the other endpoints", () => {
    const h = neighborhood(D, { kind: "node", id: "a" });
    expect([...h.nodes].sort()).toEqual(["a", "b", "c"]);
    expect([...h.edges].sort()).toEqual(["e1", "e2", "e3"]);
    expect(neighborhood(D, { kind: "node", id: "d" }).edges.size).toBe(0);
    expect([...neighborhood(D, { kind: "edge", id: "e2" }).nodes].sort()).toEqual(["a", "c"]);
    expect(neighborhood(D, null).nodes.size).toBe(0);
  });

  it("search matches label, text, id and type, case-insensitively", () => {
    const n = node("task:x", "TaskNode", 0, 5, "Summarize the Report");
    expect(matchesSearch(n, "")).toBe(true);
    expect(matchesSearch(n, "report")).toBe(true);
    expect(matchesSearch(n, "TASK:X")).toBe(true);
    expect(matchesSearch(n, "tasknode")).toBe(true);
    expect(matchesSearch(n, "zebra")).toBe(false);
  });

  it("indexes parallel edges between the same pair", () => {
    const p = parallelIndex(D.edges);
    expect(p.get("e1")).toEqual({ index: 0, total: 2 });
    expect(p.get("e3")).toEqual({ index: 1, total: 2 });
    expect(p.get("e2")).toEqual({ index: 0, total: 1 });
  });

  it("finds the smallest node containing an offset", () => {
    const nested = doc([node("outer", "TaskNode", 0, 50), node("inner", "ContextNode", 10, 20)], []);
    expect(nodeAtOffset(nested, "p.md", 15)?.id).toBe("inner");
    expect(nodeAtOffset(nested, "p.md", 30)?.id).toBe("outer");
    expect(nodeAtOffset(nested, "p.md", 99)).toBeNull();
    expect(nodeAtOffset(nested, "other.md", 15)).toBeNull();
  });

  it("lays out every node exactly once, without overlap, even with cycles and self loops", () => {
    const ids = ["a", "b", "c"];
    const pos = computeLayout(ids, [{ source: "a", target: "b" }, { source: "b", target: "c" }, { source: "c", target: "a" }, { source: "a", target: "a" }]);
    expect([...pos.keys()].sort()).toEqual(ids);
    const pts = [...pos.values()];
    for (let i = 0; i < pts.length; i++) for (let j = i + 1; j < pts.length; j++) {
      expect(Math.abs(pts[i].x - pts[j].x) + Math.abs(pts[i].y - pts[j].y)).toBeGreaterThan(10);
    }
  });

  it("lays out 300 nodes quickly", () => {
    const ids = Array.from({ length: 300 }, (_, i) => `n${i}`);
    const edges = ids.slice(1).map((id, i) => ({ source: ids[Math.floor(i / 2)], target: id }));
    const t0 = performance.now();
    const pos = computeLayout(ids, edges);
    expect(pos.size).toBe(300);
    expect(performance.now() - t0).toBeLessThan(3000);
  });
});
