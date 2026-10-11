"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Loader2, Moon, Play, ShieldCheck, Sun, TriangleAlert } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Editor, type EditorHandle, type Highlight } from "@/components/editor";
import { GraphCanvas } from "@/components/graph-canvas";
import { Inspector } from "@/components/inspector";
import { NodeList } from "@/components/node-list";
import { FilterBar } from "@/components/filter-bar";
import { analyze, ApiError, health, type HealthInfo } from "@/lib/api";
import { matchesSearch, nodeAtOffset, type Filters } from "@/lib/graph-view";
import { buildOffsetIndex } from "@/lib/offsets";
import { EDGE_STATUSES, NODE_TYPES, type GraphDocument, type Selection } from "@/lib/types";
import { cn } from "@/lib/utils";

const FILE = "prompt.md";

const EXAMPLE = `# Invoice review

You are an accounts-payable assistant.

1. Extract the invoice number and total from {{invoice_text}}.
2. Using the result of step 1, look up the purchase order with the search_po tool.
3. Compare the order total with the invoice total from step 2 and report mismatches.

## Rules
- Never guess a missing number.
- Keep every report under 120 words.
`;

type Pane = "editor" | "graph" | "details";

export function Workbench() {
  const editor = useRef<EditorHandle>(null);
  const [text, setText] = useState(EXAMPLE);
  const [analysis, setAnalysis] = useState<{ doc: GraphDocument; text: string } | null>(null);
  const [status, setStatus] = useState<"idle" | "loading" | "error">("idle");
  const [error, setError] = useState<string | null>(null);
  const [selection, setSelection] = useState<Selection>(null);
  const [filters, setFilters] = useState<Filters>({ types: new Set(NODE_TYPES), statuses: new Set(EDGE_STATUSES), search: "" });
  const [showUncovered, setShowUncovered] = useState(true);
  const [theme, setTheme] = useState<"dark" | "light">("dark");
  const [pane, setPane] = useState<Pane>("editor");
  const [reveal, setReveal] = useState<{ offset: number; nonce: number } | null>(null);
  const [info, setInfo] = useState<HealthInfo | null>(null);
  const abort = useRef<AbortController | null>(null);
  const nonce = useRef(0);

  useEffect(() => {
    try {
      const saved = localStorage.getItem("pg-theme");
      if (saved === "light" || saved === "dark") setTheme(saved);
    } catch {
      /* storage can be unavailable (private mode); the default theme is fine */
    }
    health().then(setInfo).catch(() => setInfo(null));
  }, []);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    try {
      localStorage.setItem("pg-theme", theme);
    } catch {
      /* ignore */
    }
  }, [theme]);

  const doc = analysis?.doc ?? null;
  const stale = analysis !== null && analysis.text !== text;

  const runAnalysis = useCallback(async () => {
    const current = editor.current?.getText() ?? text;
    abort.current?.abort();
    const ctl = new AbortController();
    abort.current = ctl;
    setStatus("loading");
    setError(null);
    try {
      const res = await analyze([{ path: FILE, text: current }], ctl.signal);
      setAnalysis({ doc: res.graph, text: current });
      setSelection(null);
      setStatus("idle");
      setPane("graph");
    } catch (e) {
      if ((e as Error).name === "AbortError") return;
      setStatus("error");
      setError(e instanceof ApiError ? `${e.code}: ${e.message}` : "The analysis service is not reachable.");
    }
  }, [text]);

  const index = useMemo(() => (analysis ? buildOffsetIndex(analysis.text) : null), [analysis]);

  const select = useCallback(
    (sel: Selection) => {
      setSelection(sel);
      if (!doc || !index || stale || !sel) return;
      let cp: number | null = null;
      if (sel.kind === "node") cp = doc.nodes.find((n) => n.id === sel.id)?.source_span.start ?? null;
      else cp = doc.edges.find((e) => e.id === sel.id)?.evidence[0]?.span.start ?? null;
      if (cp !== null) setReveal({ offset: index.toUtf16(cp), nonce: ++nonce.current });
    },
    [doc, index, stale],
  );

  const highlights: Highlight[] = useMemo(() => {
    if (!doc || !index || stale) return [];
    const out: Highlight[] = [];
    if (showUncovered) {
      for (const c of doc.coverage) {
        if (c.source_file !== FILE) continue;
        for (const s of c.uncovered_spans) out.push({ from: index.toUtf16(s.start), to: index.toUtf16(s.end), kind: "uncovered" });
      }
    }
    if (selection?.kind === "node") {
      const n = doc.nodes.find((x) => x.id === selection.id);
      if (n && n.source_file === FILE) out.push({ from: index.toUtf16(n.source_span.start), to: index.toUtf16(n.source_span.end), kind: "primary" });
    } else if (selection?.kind === "edge") {
      const e = doc.edges.find((x) => x.id === selection.id);
      for (const ev of e?.evidence ?? []) {
        if (ev.source_file === FILE) out.push({ from: index.toUtf16(ev.span.start), to: index.toUtf16(ev.span.end), kind: "evidence" });
      }
    }
    return out;
  }, [doc, index, stale, selection, showUncovered]);

  const onCaretClick = useCallback(
    (u16: number) => {
      if (!doc || !index || stale) return;
      const hit = nodeAtOffset(doc, FILE, index.toCodePoint(u16));
      setSelection(hit ? { kind: "node", id: hit.id } : null);
    },
    [doc, index, stale],
  );

  const focusEvidence = useCallback(
    (file: string, startCp: number) => {
      if (!index || file !== FILE) return;
      setReveal({ offset: index.toUtf16(startCp), nonce: ++nonce.current });
      setPane("editor");
    },
    [index],
  );

  const listed = useMemo(() => {
    if (!doc) return [];
    return doc.nodes.filter((n) => filters.types.has(n.type) && matchesSearch(n, filters.search));
  }, [doc, filters]);

  const coverage = doc?.coverage.find((c) => c.source_file === FILE);
  const pct = (n: number, total: number) => (total === 0 ? 0 : Math.round((n / total) * 100));

  return (
    <div className="flex h-dvh min-h-0 flex-col">
      <header className="flex flex-wrap items-center gap-3 border-b border-border bg-surface px-3 py-2">
        <h1 className="text-sm font-semibold tracking-tight">PromptGraphify</h1>
        <Button onClick={runAnalysis} disabled={status === "loading"} data-testid="analyze-button" aria-keyshortcuts="Control+Enter Meta+Enter">
          {status === "loading" ? <Loader2 className="size-4 animate-spin" aria-hidden /> : <Play className="size-4" aria-hidden />}
          Analyze Prompt
        </Button>
        <span className="hidden text-xs text-muted sm:inline">Ctrl/Cmd + Enter</span>
        <div className="ml-auto flex items-center gap-2">
          {info?.llm_enabled ? (
            <Badge tone="warn" data-testid="llm-badge">
              <TriangleAlert className="mr-1 size-3" aria-hidden /> LLM layer ON: prompt text is sent to {info.llm_provider ?? "the provider"}
            </Badge>
          ) : (
            <Badge tone="ok" data-testid="llm-badge">
              <ShieldCheck className="mr-1 size-3" aria-hidden /> Local analysis only: your prompt stays on this machine
            </Badge>
          )}
          <Button variant="outline" size="icon" onClick={() => setTheme(theme === "dark" ? "light" : "dark")} aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} theme`}>
            {theme === "dark" ? <Sun className="size-4" aria-hidden /> : <Moon className="size-4" aria-hidden />}
          </Button>
        </div>
      </header>

      <nav className="grid grid-cols-3 border-b border-border text-xs lg:hidden" aria-label="Panels">
        {(["editor", "graph", "details"] as Pane[]).map((p) => (
          <button key={p} type="button" aria-pressed={pane === p} onClick={() => setPane(p)} className={cn("py-2 capitalize", pane === p ? "bg-surface-2 text-fg" : "text-muted")}>
            {p}
          </button>
        ))}
      </nav>

      <main className="grid min-h-0 flex-1 grid-cols-1 lg:grid-cols-[minmax(320px,38%)_minmax(0,1fr)]">
        <section className={cn("min-h-0 flex-col border-r border-border", pane === "editor" ? "flex" : "hidden", "lg:flex")} aria-label="Prompt editor">
          <div className="flex items-center gap-2 border-b border-border px-3 py-1.5 text-xs text-muted">
            <span>{FILE}</span>
            <Button variant="ghost" size="sm" onClick={() => editor.current?.setText(EXAMPLE)}>
              Load example
            </Button>
            <label className="ml-auto flex items-center gap-1.5">
              <input type="checkbox" checked={showUncovered} onChange={(e) => setShowUncovered(e.target.checked)} />
              Mark uncovered text
            </label>
          </div>
          {stale && (
            <div className="border-b border-warn/40 bg-warn/10 px-3 py-1 text-xs text-warn" role="status" data-testid="stale-banner">
              The text changed since the last analysis. Analyze again to refresh the graph and highlights.
            </div>
          )}
          {status === "error" && error && (
            <div className="border-b border-err/40 bg-err/10 px-3 py-1 text-xs text-err" role="alert" data-testid="error-banner">
              {error}
            </div>
          )}
          <div className="min-h-0 flex-1">
            <Editor ref={editor} initialText={EXAMPLE} highlights={highlights} reveal={reveal} onChange={setText} onCaretClick={onCaretClick} onSubmit={runAnalysis} />
          </div>
          {coverage && (
            <div className="flex flex-wrap gap-x-4 border-t border-border px-3 py-1.5 text-xs tabular-nums text-muted" data-testid="coverage">
              <span>
                covered {pct(coverage.covered, coverage.total)}% · structural {pct(coverage.structural, coverage.total)}% · uncovered {coverage.uncovered} of {coverage.total} chars
              </span>
            </div>
          )}
        </section>

        <section className={cn("min-h-0 min-w-0 flex-col", pane === "editor" ? "hidden" : "flex", "lg:flex")}>
          <div className={cn("min-h-0 flex-1 flex-col", pane === "details" ? "hidden" : "flex", "lg:flex")}>
            <div className="flex items-center gap-2 border-b border-border bg-surface px-3 py-1.5">
              <h2 className="text-xs font-semibold">Knowledge Graph</h2>
              {doc && (
                <span className="text-xs tabular-nums text-muted" data-testid="graph-stats">
                  {doc.nodes.length} nodes · {doc.edges.length} edges
                </span>
              )}
            </div>
            <FilterBar filters={filters} onChange={setFilters} />
            <div className="min-h-0 flex-1" data-testid="graph-area">
              {doc ? (
                <GraphCanvas doc={doc} filters={filters} selection={selection} onSelect={select} dark={theme === "dark"} />
              ) : (
                <div className="flex h-full items-center justify-center p-6 text-center text-sm text-muted" data-testid="graph-empty">
                  Press “Analyze Prompt” to build the graph from the text on the left.
                </div>
              )}
            </div>
          </div>

          <div className={cn("min-h-0 grid-cols-1 border-t border-border sm:grid-cols-[minmax(160px,34%)_1fr] lg:h-[38%]", pane === "details" ? "grid h-full" : "hidden", "lg:grid")}>
            <div className="min-h-0 overflow-hidden p-2">
              <NodeList nodes={listed} selection={selection} onSelect={select} />
            </div>
            <div className="min-h-0 overflow-auto border-l border-border p-3" aria-live="polite">
              <Inspector doc={doc} selection={selection} onSelect={select} onFocusEvidence={focusEvidence} />
            </div>
          </div>
        </section>
      </main>
    </div>
  );
}
