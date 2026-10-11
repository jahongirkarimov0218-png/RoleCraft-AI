"use client";

import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type { GraphDocument, Selection } from "@/lib/types";

/** Facts about the Execution DAG: order, critical path, metrics (each with its definition), cycles,
 *  unresolved dependencies and deliberate loops. */
export function DagPanel({
  doc,
  onSelect,
  subgraph,
  onToggleSubgraph,
}: {
  doc: GraphDocument;
  onSelect(s: Selection): void;
  subgraph: boolean;
  onToggleSubgraph(v: boolean): void;
}) {
  const dag = doc.dag;
  const label = (id: string) => doc.nodes.find((n) => n.id === id)?.label ?? id;
  const chip = (id: string, i?: number) => (
    <button
      key={`${id}-${i}`}
      type="button"
      onClick={() => onSelect({ kind: "node", id })}
      className="max-w-48 truncate rounded border border-border bg-surface px-1.5 py-0.5 text-left hover:border-accent"
    >
      {i !== undefined && <span className="mr-1 tabular-nums text-muted">{i + 1}.</span>}
      {label(id)}
    </button>
  );
  return (
    <div className="max-h-44 space-y-2 overflow-auto border-b border-border bg-surface px-3 py-2 text-xs" data-testid="dag-panel" data-status={dag.status}>
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone={dag.status === "ok" ? "ok" : dag.status === "blocked" ? "err" : "neutral"} data-testid="dag-status">
          {dag.status}
        </Badge>
        {dag.status === "blocked" && dag.acyclic_subgraph && (
          <label className="flex items-center gap-1.5">
            <input type="checkbox" checked={subgraph} onChange={(e) => onToggleSubgraph(e.target.checked)} data-testid="dag-subgraph-toggle" />
            Show the acyclic subgraph ({dag.removed_for_acyclic.length} edge(s) removed, listed below)
          </label>
        )}
        {dag.status === "empty" && <span className="text-muted">No tasks, so there is no execution order.</span>}
      </div>
      {dag.cycles.map((c, i) => (
        <div key={i} className="rounded border border-err/50 p-1.5" data-testid="dag-cycle">
          <span className="font-medium text-err">Cycle ({c.certainty}):</span>{" "}
          <span className="inline-flex flex-wrap gap-1 align-middle">{c.nodes.map((n, k) => chip(n, k))}</span>
          <div className="mt-1 text-muted">edges: {c.edges.length}; evidence spans: {c.evidence.length}</div>
        </div>
      ))}
      {dag.status === "blocked" && dag.removed_for_acyclic.length > 0 && (
        <div className="text-muted" data-testid="dag-removed">
          Removed to make it acyclic: {dag.removed_for_acyclic.map((id) => (
            <button key={id} type="button" className="mr-1 underline" onClick={() => onSelect({ kind: "edge", id })}>
              {doc.edges.find((e) => e.id === id)?.relation ?? id}
            </button>
          ))}
        </div>
      )}
      {dag.topological_order.length > 0 && (
        <div>
          <div className="mb-1 text-[10px] uppercase tracking-wide text-muted">Execution order (topological)</div>
          <div className="flex flex-wrap gap-1" data-testid="dag-order">
            {dag.topological_order.map((id, i) => chip(id, i))}
          </div>
        </div>
      )}
      {dag.critical_path.length > 0 && (
        <div>
          <div className="mb-1 text-[10px] uppercase tracking-wide text-muted">Critical path (longest chain of prerequisites)</div>
          <div className="flex flex-wrap gap-1" data-testid="dag-critical">
            {dag.critical_path.map((id, i) => chip(id, i))}
          </div>
        </div>
      )}
      {dag.unresolved.length > 0 && (
        <div data-testid="dag-unresolved">
          <div className="mb-1 text-[10px] uppercase tracking-wide text-warn">Unresolved dependencies</div>
          {dag.unresolved.map((u, i) => (
            <div key={i}>
              {chip(u.node_id)} <span className="text-muted">needs “{u.reference}”, which does not exist</span>
            </div>
          ))}
        </div>
      )}
      {dag.loops.length > 0 && (
        <div className="text-muted" data-testid="dag-loops">
          Deliberate loops (not cycles): {dag.loops.map((id) => (
            <button key={id} type="button" className={cn("mr-1 underline")} onClick={() => onSelect({ kind: "edge", id })}>
              {doc.edges.find((e) => e.id === id)?.rationale ?? id}
            </button>
          ))}
        </div>
      )}
      {dag.metrics.length > 0 && (
        <details>
          <summary className="cursor-pointer text-muted">Metrics and their definitions</summary>
          <dl className="mt-1 space-y-1">
            {dag.metrics.map((m) => (
              <div key={m.name}>
                <dt className="font-medium">
                  {m.name}: <span className="font-mono text-[11px]">{JSON.stringify(m.value)}</span>
                </dt>
                <dd className="text-muted">{m.definition}</dd>
              </div>
            ))}
          </dl>
        </details>
      )}
    </div>
  );
}
