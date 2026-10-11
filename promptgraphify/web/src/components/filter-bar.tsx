"use client";

import { useState } from "react";
import { ListFilter, Search } from "lucide-react";
import { cn } from "@/lib/utils";
import { TYPE_COLOR, TYPE_LABEL, type Filters } from "@/lib/graph-view";
import { EDGE_STATUSES, NODE_TYPES, type EdgeStatus, type NodeType } from "@/lib/types";

function toggle<T>(set: Set<T>, value: T): Set<T> {
  const next = new Set(set);
  if (next.has(value)) next.delete(value);
  else next.add(value);
  return next;
}

export function FilterBar({ filters, onChange }: { filters: Filters; onChange(f: Filters): void }) {
  const [open, setOpen] = useState(false); // chips are collapsed on narrow screens
  const chips = open ? "flex" : "hidden sm:flex";
  return (
    <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5 border-b border-border bg-surface px-3 py-2" role="group" aria-label="Graph filters">
      <label className="relative flex items-center">
        <Search className="pointer-events-none absolute left-2 size-3.5 text-muted" aria-hidden />
        <input
          type="search"
          value={filters.search}
          onChange={(e) => onChange({ ...filters, search: e.target.value })}
          placeholder="Search nodes"
          aria-label="Search nodes"
          data-testid="search"
          className="h-8 w-44 rounded-md border border-border bg-bg pl-7 pr-2 text-xs placeholder:text-muted"
        />
      </label>
      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen(!open)}
        className="flex h-8 items-center gap-1 rounded-md border border-border px-2 text-xs sm:hidden"
      >
        <ListFilter className="size-3.5" aria-hidden /> Filters
      </button>
      <div className={cn(chips, "flex-wrap gap-1")} role="group" aria-label="Node types">
        {NODE_TYPES.map((t: NodeType) => {
          const on = filters.types.has(t);
          return (
            <button
              key={t}
              type="button"
              aria-pressed={on}
              data-testid={`filter-type-${t}`}
              onClick={() => onChange({ ...filters, types: toggle(filters.types, t) })}
              className={cn(
                "flex items-center gap-1 rounded border px-1.5 py-1 text-[11px] transition-[opacity,background-color] duration-150",
                on ? "border-border bg-surface-2" : "border-border/50 opacity-45",
              )}
            >
              <span className="size-2 rounded-full" style={{ background: TYPE_COLOR[t] }} aria-hidden />
              {TYPE_LABEL[t]}
            </button>
          );
        })}
      </div>
      <div className={cn(chips, "gap-1")} role="group" aria-label="Edge status">
        {EDGE_STATUSES.map((s: EdgeStatus) => {
          const on = filters.statuses.has(s);
          return (
            <button
              key={s}
              type="button"
              aria-pressed={on}
              data-testid={`filter-status-${s}`}
              onClick={() => onChange({ ...filters, statuses: toggle(filters.statuses, s) })}
              className={cn(
                "rounded border px-1.5 py-1 text-[11px] transition-[opacity,background-color] duration-150",
                on ? "border-border bg-surface-2" : "border-border/50 opacity-45",
              )}
            >
              {s.toLowerCase()}
            </button>
          );
        })}
      </div>
    </div>
  );
}
