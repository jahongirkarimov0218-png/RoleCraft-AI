"use client";

import { useEffect, useState } from "react";
import { Play } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ApiError, listQueries, runQuery } from "@/lib/api";
import type { QueryResult, QueryRow, QuerySpec } from "@/lib/types";

const BASIS_TONE = { explicit: "ok", inferred: "warn", mixed: "accent", structural: "neutral" } as const;

/** The eight named queries. Answers come from the stored graph only; every row cites its source evidence. */
export function QueriesPanel({
  graphId,
  onPickRow,
}: {
  graphId: string | null;
  onPickRow(row: QueryRow): void;
}) {
  const [specs, setSpecs] = useState<QuerySpec[]>([]);
  const [name, setName] = useState("unused_variables");
  const [params, setParams] = useState<Record<string, string>>({});
  const [result, setResult] = useState<QueryResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listQueries().then(setSpecs).catch(() => setSpecs([]));
  }, []);
  useEffect(() => {
    setResult(null);
    setError(null);
  }, [graphId]);

  const spec = specs.find((q) => q.name === name);

  async function run(override?: Record<string, string>) {
    if (!graphId) return;
    setError(null);
    try {
      setResult(await runQuery(graphId, name, override ?? params));
    } catch (e) {
      setResult(null);
      setError(e instanceof ApiError ? `${e.code}: ${e.message}` : "The query service is not reachable.");
    }
  }

  return (
    <div className="flex h-full min-h-0 flex-col gap-2 text-xs" data-testid="queries">
      <label className="flex flex-col gap-1">
        <span className="text-muted">Question</span>
        <select
          value={name}
          onChange={(e) => {
            setName(e.target.value);
            setParams({});
            setResult(null);
          }}
          data-testid="query-select"
          className="h-8 rounded-md border border-border bg-bg px-2"
        >
          {specs.map((q) => (
            <option key={q.name} value={q.name}>
              {q.question}
            </option>
          ))}
        </select>
      </label>
      {spec && (
        <>
          <p className="text-muted" data-testid="query-definition">{spec.definition}</p>
          {spec.params.map((p) => (
            <label key={p.name} className="flex flex-col gap-1">
              <span className="text-muted">
                {p.name}
                {p.required ? " *" : ""} — {p.description}
              </span>
              <input
                value={params[p.name] ?? ""}
                onChange={(e) => setParams({ ...params, [p.name]: e.target.value })}
                data-testid={`query-param-${p.name}`}
                className="h-8 rounded-md border border-border bg-bg px-2"
              />
            </label>
          ))}
        </>
      )}
      <Button size="sm" onClick={() => run()} disabled={!graphId || !spec} data-testid="query-run" className="self-start">
        <Play className="size-3" aria-hidden /> Run query
      </Button>
      {error && (
        <p className="text-err" role="alert">
          {error}
        </p>
      )}
      {result && (
        <div className="min-h-0 flex-1 space-y-1.5 overflow-auto" data-testid="query-result" data-status={result.status}>
          <p className="font-medium">{result.summary}</p>
          {result.status === "ambiguous" && (
            <ul className="space-y-1" aria-label="Candidates">
              {result.candidates.map((c) => (
                <li key={c.id}>
                  <button
                    type="button"
                    onClick={() => {
                      const key = spec?.params.find((p) => params[p.name] && result.params[p.name])?.name ?? spec?.params[0]?.name ?? "";
                      const next = { ...params, [key]: c.id };
                      setParams(next);
                      void run(next);
                    }}
                    className="w-full rounded border border-border px-1.5 py-1 text-left hover:border-accent"
                  >
                    {c.label} <span className="text-muted">({c.type})</span>
                  </button>
                </li>
              ))}
            </ul>
          )}
          <ul className="space-y-1.5">
            {result.rows.map((row, i) => (
              <li key={i}>
                <button
                  type="button"
                  data-testid="query-row"
                  onClick={() => onPickRow(row)}
                  className="w-full rounded border border-border bg-surface p-2 text-left hover:border-accent"
                >
                  <div className="flex items-center gap-1.5">
                    <Badge tone={BASIS_TONE[row.basis]}>{row.basis}</Badge>
                    <span className="font-medium">{row.title}</span>
                  </div>
                  <p className="mt-1 break-words text-muted">{row.detail}</p>
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
