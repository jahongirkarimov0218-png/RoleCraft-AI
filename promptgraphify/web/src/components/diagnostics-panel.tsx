"use client";

import { useState } from "react";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import type { Diagnostic, Severity } from "@/lib/types";

const TONE = { error: "err", warning: "warn", info: "neutral" } as const;
const ORDER: Severity[] = ["error", "warning", "info"];

/** Diagnostics list. Each entry is keyboard reachable; picking one selects the affected node and marks the
 *  evidence in the editor. "proven" follows from the graph or source; "probable" is a heuristic. */
export function DiagnosticsPanel({
  diagnostics,
  activeId,
  onPick,
}: {
  diagnostics: Diagnostic[];
  activeId: string | null;
  onPick(d: Diagnostic): void;
}) {
  const [shown, setShown] = useState<Set<Severity>>(new Set(ORDER));
  const list = diagnostics.filter((d) => shown.has(d.severity));
  const count = (s: Severity) => diagnostics.filter((d) => d.severity === s).length;
  return (
    <div className="flex h-full min-h-0 flex-col gap-2" data-testid="diagnostics">
      <div className="flex flex-wrap gap-1" role="group" aria-label="Severity filter">
        {ORDER.map((s) => (
          <button
            key={s}
            type="button"
            aria-pressed={shown.has(s)}
            data-testid={`diag-filter-${s}`}
            onClick={() => {
              const next = new Set(shown);
              if (next.has(s)) next.delete(s);
              else next.add(s);
              setShown(next);
            }}
            className={cn("rounded border px-1.5 py-1 text-[11px]", shown.has(s) ? "border-border bg-surface-2" : "border-border/50 opacity-45")}
          >
            {s} {count(s)}
          </button>
        ))}
      </div>
      {diagnostics.length === 0 && <p className="text-xs text-muted" data-testid="diag-none">No diagnostics for this input.</p>}
      <ul className="min-h-0 flex-1 space-y-1.5 overflow-auto" aria-label="Diagnostics">
        {list.map((d) => (
          <li key={d.id}>
            <button
              type="button"
              data-testid="diagnostic"
              data-rule={d.rule_id}
              onClick={() => onPick(d)}
              className={cn(
                "w-full rounded border bg-surface p-2 text-left text-xs hover:border-accent",
                d.id === activeId ? "border-accent" : "border-border",
              )}
            >
              <div className="flex flex-wrap items-center gap-1.5">
                <Badge tone={TONE[d.severity]}>{d.severity}</Badge>
                <Badge tone={d.certainty === "proven" ? "ok" : "warn"} title={d.certainty === "proven" ? "follows from the source or the graph" : "heuristic: a probable finding, not a proof"}>
                  {d.certainty}
                </Badge>
                <code className="text-[11px] text-muted">{d.rule_id}</code>
              </div>
              <p className="mt-1 break-words">{d.description}</p>
              {d.id === activeId && (
                <p className="mt-1 break-words text-muted">
                  <span className="font-medium text-fg">Fix: </span>
                  {d.suggested_fix}
                </p>
              )}
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
