"use client";

import { memo, useCallback, useEffect, useMemo, useState } from "react";
import {
  Background,
  BaseEdge,
  Controls,
  Handle,
  MarkerType,
  MiniMap,
  Panel,
  Position,
  ReactFlow,
  ReactFlowProvider,
  getBezierPath,
  useReactFlow,
  useStore,
  type Edge as RFEdge,
  type EdgeProps,
  type Node as RFNode,
  type NodeChange,
  type NodeProps,
} from "@xyflow/react";
import { Maximize2 } from "lucide-react";
import { cn } from "@/lib/utils";
import {
  NODE_H,
  NODE_W,
  STATUS_DASH,
  TYPE_COLOR,
  TYPE_LABEL,
  computeLayout,
  matchesSearch,
  neighborhood,
  parallelIndex,
  visibleIds,
  type Filters,
  type Positions,
} from "@/lib/graph-view";
import type { GraphDocument, GraphEdge, GraphNode, Selection } from "@/lib/types";

interface NodeData extends Record<string, unknown> {
  node: GraphNode;
  dimmed: boolean;
  matched: boolean;
}
type PNode = RFNode<NodeData, "prompt">;

const PromptNode = memo(function PromptNode({ data, selected }: NodeProps<PNode>) {
  const n = data.node;
  const color = TYPE_COLOR[n.type];
  const undefinedRef = n.metadata?.defined === false || n.metadata?.declared === false;
  return (
    <div
      data-testid="graph-node"
      data-node-type={n.type}
      data-node-id={n.id}
      title={n.original_text}
      className={cn(
        "rounded-md border bg-surface px-2.5 py-1.5 text-xs shadow-sm transition-[opacity,box-shadow] duration-150",
        selected && "ring-2 ring-accent",
        data.matched && "ring-2 ring-warn",
        data.dimmed && "opacity-25",
      )}
      style={{ width: NODE_W, minHeight: NODE_H - 8, borderColor: color }}
    >
      <Handle type="target" position={Position.Left} className="!size-1 !min-h-0 !min-w-0 !border-0 !bg-transparent" />
      <div className="flex items-center gap-1.5 text-[10px] uppercase tracking-wide text-muted">
        <span className="size-2 rounded-full" style={{ background: color }} aria-hidden />
        <span>{TYPE_LABEL[n.type]}</span>
        {undefinedRef && <span className="ml-auto text-warn">unresolved</span>}
        {n.confidence < 1 && <span className="ml-auto tabular-nums">{n.confidence.toFixed(2)}</span>}
      </div>
      <div className="mt-1 line-clamp-2 break-words leading-snug">{n.label}</div>
      <Handle type="source" position={Position.Right} className="!size-1 !min-h-0 !min-w-0 !border-0 !bg-transparent" />
    </div>
  );
});

interface EdgeData extends Record<string, unknown> {
  edge: GraphEdge;
  dimmed: boolean;
  index: number;
  total: number;
  showLabel: boolean;
}
type REdge = RFEdge<EdgeData, "relation">;

function RelationEdge({ id, sourceX, sourceY, targetX, targetY, sourcePosition, targetPosition, data, selected, markerEnd }: EdgeProps<REdge>) {
  const idx = data?.index ?? 0;
  const total = data?.total ?? 1;
  const curvature = 0.25 + (idx - (total - 1) / 2) * 0.22;
  const [path, lx, ly] = getBezierPath({ sourceX, sourceY, targetX, targetY, sourcePosition, targetPosition, curvature });
  const status = data?.edge.status ?? "EXTRACTED";
  const color = status === "AMBIGUOUS" ? "var(--warn)" : status === "INFERRED" ? "var(--muted)" : "var(--fg)";
  return (
    <>
      <BaseEdge
        id={id}
        path={path}
        markerEnd={markerEnd}
        interactionWidth={14}
        style={{
          stroke: color,
          strokeWidth: selected ? 2.5 : 1.4,
          strokeDasharray: STATUS_DASH[status],
          opacity: data?.dimmed ? 0.12 : selected ? 1 : 0.75,
        }}
      />
      {(data?.showLabel || selected) && !data?.dimmed && (
        <text x={lx} y={ly} textAnchor="middle" dominantBaseline="central" className="pointer-events-none select-none fill-muted text-[9px]">
          {data?.edge.relation.replace(/_/g, " ").toLowerCase()}
        </text>
      )}
    </>
  );
}

const nodeTypes = { prompt: PromptNode };
const edgeTypes = { relation: RelationEdge };

interface Props {
  doc: GraphDocument;
  filters: Filters;
  selection: Selection;
  onSelect(sel: Selection): void;
  dark: boolean;
  /** Which edges and nodes to draw; the Execution DAG tab passes its own view. */
  mode?: "knowledge";
}

function Canvas({ doc, filters, selection, onSelect, dark }: Props) {
  const rf = useReactFlow();
  const visible = useMemo(() => visibleIds(doc, filters), [doc, filters]);
  const visibleNodes = useMemo(() => doc.nodes.filter((n) => visible.nodes.has(n.id)), [doc, visible]);
  const visibleEdges = useMemo(() => doc.edges.filter((e) => visible.edges.has(e.id)), [doc, visible]);

  // Portrait containers (phones) get a top-to-bottom layout, landscape ones left-to-right.
  const portrait = useStore((s) => s.height > s.width * 1.1);
  // Layout depends only on which nodes/edges exist (and the orientation), not on selection or search.
  const base: Positions = useMemo(
    () => computeLayout(visibleNodes.map((n) => n.id), visibleEdges, portrait ? "TB" : "LR"),
    [visibleNodes, visibleEdges, portrait],
  );
  const [moved, setMoved] = useState<Positions>(new Map());
  useEffect(() => setMoved(new Map()), [doc.graph_id]);

  const hood = useMemo(() => neighborhood(doc, selection), [doc, selection]);
  const hasSearch = filters.search.trim().length > 0;
  const par = useMemo(() => parallelIndex(visibleEdges), [visibleEdges]);

  const nodes: PNode[] = useMemo(
    () =>
      visibleNodes.map((n) => {
        const pos = moved.get(n.id) ?? base.get(n.id) ?? { x: 0, y: 0 };
        const matched = hasSearch && matchesSearch(n, filters.search);
        const dimmed = (selection !== null && !hood.nodes.has(n.id)) || (hasSearch && !matched);
        return {
          id: n.id,
          type: "prompt",
          position: pos,
          data: { node: n, dimmed, matched },
          selected: selection?.kind === "node" && selection.id === n.id,
          width: NODE_W,
          height: NODE_H,
        } as PNode;
      }),
    [visibleNodes, base, moved, hood, selection, hasSearch, filters.search],
  );

  const edges: REdge[] = useMemo(
    () =>
      visibleEdges.map((e) => {
        const p = par.get(e.id) ?? { index: 0, total: 1 };
        const dimmed = selection !== null && !hood.edges.has(e.id);
        return {
          id: e.id,
          type: "relation",
          source: e.source,
          target: e.target,
          selected: selection?.kind === "edge" && selection.id === e.id,
          markerEnd: { type: MarkerType.ArrowClosed, width: 14, height: 14, color: e.status === "AMBIGUOUS" ? "var(--warn)" : "var(--muted)" },
          data: { edge: e, dimmed, index: p.index, total: p.total, showLabel: visibleEdges.length <= 30 },
        } as REdge;
      }),
    [visibleEdges, par, hood, selection],
  );

  const onNodesChange = useCallback((changes: NodeChange<PNode>[]) => {
    const moves = changes.filter((c) => c.type === "position" && c.position);
    if (moves.length === 0) return;
    setMoved((prev) => {
      const next = new Map(prev);
      for (const c of moves) if (c.type === "position" && c.position) next.set(c.id, c.position);
      return next;
    });
  }, []);

  // Fit the view whenever a different graph (or filter set) is drawn.
  useEffect(() => {
    const t = setTimeout(() => rf.fitView({ padding: 0.15, duration: 200 }), 30);
    return () => clearTimeout(t);
  }, [doc.graph_id, visibleNodes.length, portrait, rf]);

  // Bring a selected node into view when it was chosen elsewhere (list, editor).
  useEffect(() => {
    if (selection?.kind !== "node") return;
    const n = rf.getNode(selection.id);
    if (!n) return;
    rf.setCenter(n.position.x + NODE_W / 2, n.position.y + NODE_H / 2, { zoom: Math.max(rf.getZoom(), 0.8), duration: 250 });
  }, [selection, rf]);

  return (
    <ReactFlow
      nodes={nodes}
      edges={edges}
      nodeTypes={nodeTypes}
      edgeTypes={edgeTypes}
      onNodesChange={onNodesChange}
      onNodeClick={(_, n) => onSelect({ kind: "node", id: n.id })}
      onEdgeClick={(_, e) => onSelect({ kind: "edge", id: e.id })}
      onPaneClick={() => onSelect(null)}
      colorMode={dark ? "dark" : "light"}
      nodesConnectable={false}
      elementsSelectable
      onlyRenderVisibleElements={doc.nodes.length > 60}
      minZoom={0.1}
      maxZoom={2}
      proOptions={{ hideAttribution: true }}
      aria-label="Knowledge graph"
    >
      <Background gap={24} size={1} />
      <Controls showInteractive={false} position="bottom-left" />
      <MiniMap className="!hidden sm:!block" pannable zoomable position="bottom-right" nodeColor={(n) => TYPE_COLOR[(n.data as NodeData).node.type]} maskColor="rgba(0,0,0,0.35)" />
      <Panel position="top-right">
        <button
          type="button"
          onClick={() => rf.fitView({ padding: 0.15, duration: 200 })}
          className="flex items-center gap-1 rounded-md border border-border bg-surface px-2 py-1 text-xs hover:bg-surface-2"
          aria-label="Fit view"
          data-testid="fit-view"
        >
          <Maximize2 className="size-3" aria-hidden /> Fit
        </button>
      </Panel>
    </ReactFlow>
  );
}

export function GraphCanvas(props: Props) {
  return (
    <div className="h-full w-full" data-testid="graph-canvas">
      <ReactFlowProvider>
        <Canvas {...props} />
      </ReactFlowProvider>
    </div>
  );
}
