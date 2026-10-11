"use client";

import { ArrowRight } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { TYPE_COLOR, TYPE_LABEL } from "@/lib/graph-view";
import type { GraphDocument, GraphEdge, GraphNode, Selection } from "@/lib/types";

const STATUS_TONE = { EXTRACTED: "ok", INFERRED: "accent", AMBIGUOUS: "warn" } as const;

function Row({ k, children }: { k: string; children: React.ReactNode }) {
  return (
    <div className="grid grid-cols-[88px_1fr] gap-2 py-0.5 text-xs">
      <dt className="text-muted">{k}</dt>
      <dd className="min-w-0 break-words">{children}</dd>
    </div>
  );
}

function EvidenceList({ edge, onFocusEvidence }: { edge: GraphEdge; onFocusEvidence(file: string, start: number): void }) {
  return (
    <ul className="space-y-1.5" data-testid="evidence-list">
      {edge.evidence.map((ev, i) => (
        <li key={i}>
          <button
            type="button"
            onClick={() => onFocusEvidence(ev.source_file, ev.span.start)}
            className="w-full rounded border border-border bg-surface-2 p-1.5 text-left font-mono text-[11px] hover:border-accent"
          >
            <span className="mr-1 text-muted tabular-nums">
              {ev.source_file}:{ev.span.start}-{ev.span.end}
            </span>
            <span className="whitespace-pre-wrap break-words">{ev.text}</span>
          </button>
        </li>
      ))}
    </ul>
  );
}

function NodeCard({ doc, node, onSelect }: { doc: GraphDocument; node: GraphNode; onSelect(s: Selection): void }) {
  const out = doc.edges.filter((e) => e.source === node.id);
  const inc = doc.edges.filter((e) => e.target === node.id);
  const labelOf = (id: string) => doc.nodes.find((n) => n.id === id)?.label ?? id;
  const meta = Object.entries(node.metadata ?? {}).filter(([k]) => k !== "usage_spans");
  return (
    <div data-testid="inspector" data-kind="node" className="space-y-3">
      <div className="flex items-center gap-2">
        <span className="size-2.5 rounded-full" style={{ background: TYPE_COLOR[node.type] }} aria-hidden />
        <h2 className="text-sm font-semibold" data-testid="inspector-title">
          {TYPE_LABEL[node.type]}
        </h2>
        <Badge tone={node.validation_status === "verified" ? "ok" : "warn"}>{node.validation_status}</Badge>
        <Badge>{node.extraction_method}</Badge>
      </div>
      <div>
        <div className="mb-1 text-[10px] uppercase tracking-wide text-muted">Original text (exact source span)</div>
        <pre
          data-testid="inspector-original-text"
          className="max-h-48 overflow-auto whitespace-pre-wrap break-words rounded border border-border bg-surface-2 p-2 font-mono text-xs"
        >
          {node.original_text}
        </pre>
        {node.decoded_text && node.decoded_text !== node.original_text && (
          <>
            <div className="mb-1 mt-2 text-[10px] uppercase tracking-wide text-muted">Decoded view</div>
            <pre className="whitespace-pre-wrap break-words rounded border border-border bg-surface-2 p-2 font-mono text-xs">{node.decoded_text}</pre>
          </>
        )}
      </div>
      <dl>
        <Row k="Description">{node.description}</Row>
        <Row k="Source span">
          <span className="tabular-nums" data-testid="inspector-span">
            {node.source_file} [{node.source_span.start}, {node.source_span.end}) code points
          </span>
          {node.metadata?.span_precision === "enclosing" && <Badge tone="warn" className="ml-1">enclosing</Badge>}
        </Row>
        <Row k="Confidence">
          <span className="tabular-nums">{node.confidence}</span>
        </Row>
        <Row k="Role scope">
          {node.role_scope.role ?? "—"}
          {node.role_scope.agent ? ` · agent ${node.role_scope.agent}` : ""}
        </Row>
        <Row k="ID">
          <code className="text-[11px]">{node.id}</code>
        </Row>
      </dl>
      <details className="text-xs">
        <summary className="cursor-pointer text-muted">Metadata</summary>
        <pre className="mt-1 overflow-auto rounded border border-border bg-surface-2 p-2 font-mono text-[11px]">
          {JSON.stringify(Object.fromEntries(meta), null, 2)}
        </pre>
      </details>
      {[
        ["Outgoing", out, (e: GraphEdge) => e.target],
        ["Incoming", inc, (e: GraphEdge) => e.source],
      ].map(([title, list, other]) => (
        <div key={title as string}>
          <div className="mb-1 text-[10px] uppercase tracking-wide text-muted">
            {title as string} ({(list as GraphEdge[]).length})
          </div>
          <ul className="space-y-1">
            {(list as GraphEdge[]).map((e) => (
              <li key={e.id}>
                <button
                  type="button"
                  onClick={() => onSelect({ kind: "edge", id: e.id })}
                  className="flex w-full items-center gap-1.5 rounded border border-border px-1.5 py-1 text-left text-xs hover:border-accent"
                >
                  <Badge tone={STATUS_TONE[e.status]}>{e.status[0]}</Badge>
                  <span className="text-muted">{e.relation}</span>
                  <ArrowRight className="size-3 shrink-0 text-muted" aria-hidden />
                  <span className="truncate">{labelOf((other as (e: GraphEdge) => string)(e))}</span>
                </button>
              </li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  );
}

function EdgeCard({
  doc,
  edge,
  onSelect,
  onFocusEvidence,
}: {
  doc: GraphDocument;
  edge: GraphEdge;
  onSelect(s: Selection): void;
  onFocusEvidence(file: string, start: number): void;
}) {
  const src = doc.nodes.find((n) => n.id === edge.source);
  const tgt = doc.nodes.find((n) => n.id === edge.target);
  return (
    <div data-testid="inspector" data-kind="edge" className="space-y-3">
      <div className="flex flex-wrap items-center gap-2">
        <h2 className="text-sm font-semibold" data-testid="inspector-title">
          {edge.relation}
        </h2>
        <Badge tone={STATUS_TONE[edge.status]} data-testid="edge-status">
          {edge.status}
        </Badge>
        <Badge>{edge.extraction_method}</Badge>
      </div>
      <div className="flex items-center gap-2 text-xs">
        <button type="button" className="min-w-0 flex-1 truncate rounded border border-border px-1.5 py-1 text-left hover:border-accent" onClick={() => src && onSelect({ kind: "node", id: src.id })}>
          {src?.label ?? edge.source}
        </button>
        <ArrowRight className="size-3 shrink-0 text-muted" aria-hidden />
        <button type="button" className="min-w-0 flex-1 truncate rounded border border-border px-1.5 py-1 text-left hover:border-accent" onClick={() => tgt && onSelect({ kind: "node", id: tgt.id })}>
          {tgt?.label ?? edge.target}
        </button>
      </div>
      <dl>
        <Row k="Rationale">
          <span data-testid="edge-rationale">{edge.rationale}</span>
        </Row>
        {edge.reference && (
          <Row k="Reference">
            <code className="text-[11px]" data-testid="edge-reference">{edge.reference}</code>
          </Row>
        )}
        {edge.rule && <Row k="Rule">{edge.rule}</Row>}
        <Row k="Confidence">
          <span className="tabular-nums">{edge.confidence}</span>
        </Row>
        {Object.keys(edge.metadata ?? {}).length > 0 && (
          <Row k="Metadata">
            <code className="text-[11px]">{JSON.stringify(edge.metadata)}</code>
          </Row>
        )}
      </dl>
      <div>
        <div className="mb-1 text-[10px] uppercase tracking-wide text-muted">Evidence ({edge.evidence.length})</div>
        <EvidenceList edge={edge} onFocusEvidence={onFocusEvidence} />
      </div>
    </div>
  );
}

export function Inspector({
  doc,
  selection,
  onSelect,
  onFocusEvidence,
}: {
  doc: GraphDocument | null;
  selection: Selection;
  onSelect(s: Selection): void;
  onFocusEvidence(file: string, start: number): void;
}) {
  if (!doc) {
    return <p className="p-3 text-xs text-muted">Analyze a prompt, then select a node or an edge to see its source span, purpose and links.</p>;
  }
  if (!selection) {
    return (
      <p className="p-3 text-xs text-muted" data-testid="inspector-empty">
        Select a node or an edge in the graph, in the node list, or click a highlighted span in the editor.
      </p>
    );
  }
  if (selection.kind === "node") {
    const node = doc.nodes.find((n) => n.id === selection.id);
    return node ? <NodeCard doc={doc} node={node} onSelect={onSelect} /> : null;
  }
  const edge = doc.edges.find((e) => e.id === selection.id);
  return edge ? <EdgeCard doc={doc} edge={edge} onSelect={onSelect} onFocusEvidence={onFocusEvidence} /> : null;
}
