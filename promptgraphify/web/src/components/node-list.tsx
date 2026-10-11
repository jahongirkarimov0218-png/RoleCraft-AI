"use client";

import { useEffect, useRef } from "react";
import { cn } from "@/lib/utils";
import { TYPE_COLOR, TYPE_LABEL } from "@/lib/graph-view";
import { isLlm, type GraphNode, type Selection } from "@/lib/types";

/** Keyboard-navigable list of the nodes (ARIA listbox: arrows move, Enter / Space selects, Esc clears). */
export function NodeList({
  nodes,
  selection,
  onSelect,
}: {
  nodes: GraphNode[];
  selection: Selection;
  onSelect(sel: Selection): void;
}) {
  const refs = useRef<Map<string, HTMLLIElement>>(new Map());
  const selectedId = selection?.kind === "node" ? selection.id : null;

  useEffect(() => {
    if (selectedId) refs.current.get(selectedId)?.scrollIntoView({ block: "nearest" });
  }, [selectedId]);

  function move(delta: number) {
    if (nodes.length === 0) return;
    const i = selectedId ? nodes.findIndex((n) => n.id === selectedId) : -1;
    const next = Math.min(nodes.length - 1, Math.max(0, i + delta));
    onSelect({ kind: "node", id: nodes[next].id });
  }

  if (nodes.length === 0) return <p className="rounded-md border border-border bg-surface p-2 text-xs text-muted">No nodes match.</p>;
  return (
    <ul
      role="listbox"
      aria-label="Nodes"
      tabIndex={0}
      aria-activedescendant={selectedId ? `node-opt-${selectedId}` : undefined}
      data-testid="node-list"
      className="max-h-full overflow-auto rounded-md border border-border bg-surface"
      onKeyDown={(e) => {
        if (e.key === "ArrowDown") (e.preventDefault(), move(1));
        else if (e.key === "ArrowUp") (e.preventDefault(), move(-1));
        else if (e.key === "Home") (e.preventDefault(), nodes[0] && onSelect({ kind: "node", id: nodes[0].id }));
        else if (e.key === "End") (e.preventDefault(), nodes.length && onSelect({ kind: "node", id: nodes[nodes.length - 1].id }));
        else if (e.key === "Escape") onSelect(null);
      }}
    >
      {nodes.map((n) => (
        <li
          key={n.id}
          id={`node-opt-${n.id}`}
          role="option"
          aria-selected={n.id === selectedId}
          ref={(el) => {
            if (el) refs.current.set(n.id, el);
            else refs.current.delete(n.id);
          }}
          onClick={() => onSelect({ kind: "node", id: n.id })}
          className={cn(
            "flex cursor-pointer items-center gap-2 border-b border-border/60 px-2 py-1.5 text-xs last:border-0 hover:bg-surface-2",
            n.id === selectedId && "bg-surface-2 ring-1 ring-inset ring-accent",
          )}
        >
          <span className="size-2 shrink-0 rounded-full" style={{ background: TYPE_COLOR[n.type] }} aria-hidden />
          <span className="w-16 shrink-0 text-[10px] uppercase tracking-wide text-muted">{TYPE_LABEL[n.type]}</span>
          <span className="truncate">{n.label}</span>
          {isLlm(n) && <span className="ml-auto shrink-0 text-[10px] text-warn">LLM</span>}
        </li>
      ))}
    </ul>
  );
}
