"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Loader2, Moon, Play, Plus, ShieldCheck, Sun, TriangleAlert, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Editor, type Highlight } from "@/components/editor";
import { GraphCanvas } from "@/components/graph-canvas";
import { Inspector } from "@/components/inspector";
import { NodeList } from "@/components/node-list";
import { FilterBar } from "@/components/filter-bar";
import { DiagnosticsPanel } from "@/components/diagnostics-panel";
import { QueriesPanel } from "@/components/queries-panel";
import { DagPanel } from "@/components/dag-panel";
import { analyze, ApiError, health, type HealthInfo } from "@/lib/api";
import { dagView, knowledgeView, matchesSearch, nodeAtOffset, type Filters } from "@/lib/graph-view";
import { buildOffsetIndex, type OffsetIndex } from "@/lib/offsets";
import { EDGE_STATUSES, NODE_TYPES, type Diagnostic, type GraphDocument, type QueryRow, type Selection } from "@/lib/types";
import { cn } from "@/lib/utils";

const EXAMPLE = `# Invoice review

You are an accounts-payable assistant.

1. Extract the invoice number and total from {{invoice_text}}.
2. Using the result of step 1, look up the purchase order with the search_po tool.
3. Compare the order total with the invoice total from step 2 and report mismatches.

## Rules
- Never guess a missing number.
- Keep every report under 120 words.
`;

interface FileTab {
  id: number;
  name: string;
  text: string;
  rev: number; // bumped when the text is replaced from outside the editor, which remounts it
}
type Pane = "editor" | "graph" | "details";
interface Analysis {
  doc: GraphDocument;
  files: { name: string; text: string }[];
  indexes: Map<string, OffsetIndex>;
}

export function Workbench() {
  const nextId = useRef(2);
  const [files, setFiles] = useState<FileTab[]>([{ id: 1, name: "prompt.md", text: EXAMPLE, rev: 0 }]);
  const [activeId, setActiveId] = useState(1);
  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const [status, setStatus] = useState<"idle" | "loading" | "error">("idle");
  const [error, setError] = useState<string | null>(null);
  const [selection, setSelection] = useState<Selection>(null);
  const [focusDiag, setFocusDiag] = useState<Diagnostic | null>(null);
  const [extraEvidence, setExtraEvidence] = useState<{ file: string; from: number; to: number }[]>([]);
  const [filters, setFilters] = useState<Filters>({ types: new Set(NODE_TYPES), statuses: new Set(EDGE_STATUSES), search: "" });
  const [view, setView] = useState<"graph" | "dag">("graph");
  const [bottom, setBottom] = useState<"nodes" | "diagnostics" | "queries">("nodes");
  const [subgraph, setSubgraph] = useState(false);
  const [showUncovered, setShowUncovered] = useState(true);
  const [theme, setTheme] = useState<"dark" | "light">("dark");
  const [pane, setPane] = useState<Pane>("editor");
  const [reveal, setReveal] = useState<{ offset: number; nonce: number } | null>(null);
  const [info, setInfo] = useState<HealthInfo | null>(null);
  const abort = useRef<AbortController | null>(null);
  const nonce = useRef(0);

  const active = files.find((f) => f.id === activeId) ?? files[0];

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
  const snapshotOf = (name: string) => analysis?.files.find((f) => f.name === name);
  // The graph describes the text that was analysed; any edit since then makes spans untrustworthy.
  const stale =
    analysis !== null &&
    (analysis.files.length !== files.length || files.some((f) => snapshotOf(f.name)?.text !== f.text));
  const activeFresh = analysis !== null && snapshotOf(active.name)?.text === active.text;

  const runAnalysis = useCallback(async () => {
    abort.current?.abort();
    const ctl = new AbortController();
    abort.current = ctl;
    setStatus("loading");
    setError(null);
    const snapshot = files.map((f) => ({ name: f.name, text: f.text }));
    try {
      const res = await analyze(snapshot.map((f) => ({ path: f.name, text: f.text })), ctl.signal);
      setAnalysis({ doc: res.graph, files: snapshot, indexes: new Map(snapshot.map((f) => [f.name, buildOffsetIndex(f.text)])) });
      setSelection(null);
      setFocusDiag(null);
      setExtraEvidence([]);
      setStatus("idle");
      setPane("graph");
    } catch (e) {
      if ((e as Error).name === "AbortError") return;
      setStatus("error");
      setError(e instanceof ApiError ? `${e.code}: ${e.message}` : "The analysis service is not reachable.");
    }
  }, [files]);

  const goTo = useCallback(
    (file: string, cp: number) => {
      const tab = files.find((f) => f.name === file);
      const idx = analysis?.indexes.get(file);
      if (!tab || !idx) return;
      if (tab.id !== activeId) setActiveId(tab.id);
      setReveal({ offset: idx.toUtf16(cp), nonce: ++nonce.current });
    },
    [files, activeId, analysis],
  );

  const select = useCallback(
    (sel: Selection) => {
      setSelection(sel);
      setFocusDiag(null);
      setExtraEvidence([]);
      if (!doc || !sel) return;
      if (sel.kind === "node") {
        const n = doc.nodes.find((x) => x.id === sel.id);
        if (n) goTo(n.source_file, n.source_span.start);
      } else {
        const ev = doc.edges.find((e) => e.id === sel.id)?.evidence[0];
        if (ev) goTo(ev.source_file, ev.span.start);
      }
    },
    [doc, goTo],
  );

  const pickDiagnostic = useCallback(
    (d: Diagnostic) => {
      setFocusDiag(d);
      setExtraEvidence([]);
      const node = d.affected_nodes[0];
      setSelection(node ? { kind: "node", id: node } : null);
      const ev = d.evidence[0];
      if (ev) goTo(ev.source_file, ev.span.start);
    },
    [goTo],
  );

  const pickQueryRow = useCallback(
    (row: QueryRow) => {
      setFocusDiag(null);
      const first = row.node_ids[0];
      setSelection(first ? { kind: "node", id: first } : null);
      setExtraEvidence(row.evidence.map((e) => ({ file: e.source_file, from: e.span.start, to: e.span.end })));
      const ev = row.evidence[0];
      if (ev) goTo(ev.source_file, ev.span.start);
    },
    [goTo],
  );

  const highlights: Highlight[] = useMemo(() => {
    if (!doc || !analysis || !activeFresh) return [];
    const idx = analysis.indexes.get(active.name);
    if (!idx) return [];
    const out: Highlight[] = [];
    const put = (file: string, a: number, b: number, kind: Highlight["kind"]) => {
      if (file === active.name) out.push({ from: idx.toUtf16(a), to: idx.toUtf16(b), kind });
    };
    if (showUncovered) {
      for (const c of doc.coverage) for (const s of c.uncovered_spans) put(c.source_file, s.start, s.end, "uncovered");
    }
    for (const e of extraEvidence) put(e.file, e.from, e.to, "evidence");
    for (const ev of focusDiag?.evidence ?? []) put(ev.source_file, ev.span.start, ev.span.end, "evidence");
    if (selection?.kind === "node") {
      const n = doc.nodes.find((x) => x.id === selection.id);
      if (n) put(n.source_file, n.source_span.start, n.source_span.end, "primary");
    } else if (selection?.kind === "edge") {
      const e = doc.edges.find((x) => x.id === selection.id);
      for (const ev of e?.evidence ?? []) put(ev.source_file, ev.span.start, ev.span.end, "evidence");
    }
    return out;
  }, [doc, analysis, activeFresh, active.name, selection, showUncovered, focusDiag, extraEvidence]);

  const onCaretClick = useCallback(
    (u16: number) => {
      const idx = analysis?.indexes.get(active.name);
      if (!doc || !idx || !activeFresh) return;
      const hit = nodeAtOffset(doc, active.name, idx.toCodePoint(u16));
      setFocusDiag(null);
      setExtraEvidence([]);
      setSelection(hit ? { kind: "node", id: hit.id } : null);
    },
    [doc, analysis, active.name, activeFresh],
  );

  const listed = useMemo(() => {
    if (!doc) return [];
    return doc.nodes.filter((n) => filters.types.has(n.type) && matchesSearch(n, filters.search));
  }, [doc, filters]);

  const kg = useMemo(() => (doc ? knowledgeView(doc, filters) : null), [doc, filters]);
  const dag = useMemo(() => (doc ? dagView(doc, filters, subgraph) : null), [doc, filters, subgraph]);

  const coverage = doc?.coverage.find((c) => c.source_file === active.name);
  const pct = (n: number, total: number) => (total === 0 ? 0 : Math.round((n / total) * 100));

  const addFile = () => {
    const id = nextId.current++;
    setFiles((fs) => [...fs, { id, name: `file-${id}.md`, text: "", rev: 0 }]);
    setActiveId(id);
  };
  const removeFile = (id: number) => {
    setFiles((fs) => {
      const rest = fs.filter((f) => f.id !== id);
      if (id === activeId && rest[0]) setActiveId(rest[0].id);
      return rest;
    });
  };
  const rename = (id: number, name: string) => setFiles((fs) => fs.map((f) => (f.id === id ? { ...f, name } : f)));

  const counts = {
    error: doc?.diagnostics.filter((d) => d.severity === "error").length ?? 0,
    all: doc?.diagnostics.length ?? 0,
  };

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
          <div className="flex items-center gap-1 overflow-x-auto border-b border-border px-2 py-1 text-xs" role="tablist" aria-label="Files" data-testid="file-tabs">
            {files.map((f) => (
              <div key={f.id} className={cn("flex items-center rounded border", f.id === activeId ? "border-accent bg-surface-2" : "border-border")}>
                {f.id === activeId ? (
                  <input
                    value={f.name}
                    onChange={(e) => rename(f.id, e.target.value)}
                    aria-label="File name"
                    data-testid="file-name"
                    className="h-7 w-28 bg-transparent px-1.5"
                  />
                ) : (
                  <button type="button" role="tab" onClick={() => setActiveId(f.id)} className="h-7 px-2" data-testid="file-tab">
                    {f.name}
                  </button>
                )}
                {files.length > 1 && (
                  <button type="button" onClick={() => removeFile(f.id)} aria-label={`Remove ${f.name}`} className="px-1 text-muted hover:text-fg">
                    <X className="size-3" aria-hidden />
                  </button>
                )}
              </div>
            ))}
            <Button variant="ghost" size="icon" onClick={addFile} aria-label="Add file" data-testid="add-file" className="size-7">
              <Plus className="size-3.5" aria-hidden />
            </Button>
            <label className="ml-auto flex shrink-0 items-center gap-1.5 text-muted">
              <input type="checkbox" checked={showUncovered} onChange={(e) => setShowUncovered(e.target.checked)} />
              Mark uncovered
            </label>
          </div>
          <div className="flex items-center gap-2 border-b border-border px-3 py-1 text-[11px] text-muted">
            <span>Format from extension: .md .txt .xml .yaml .json</span>
            <Button variant="ghost" size="sm" onClick={() => setFiles((fs) => fs.map((f) => (f.id === active.id ? { ...f, text: EXAMPLE, rev: f.rev + 1 } : f)))}>
              Load example
            </Button>
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
            <Editor
              key={`${active.id}:${active.rev}`}
              initialText={active.text}
              highlights={highlights}
              reveal={reveal}
              onChange={(text) => setFiles((fs) => fs.map((f) => (f.id === active.id ? (f.text === text ? f : { ...f, text }) : f)))}
              onCaretClick={onCaretClick}
              onSubmit={runAnalysis}
            />
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
            <Tabs value={view} onValueChange={(v) => setView(v as "graph" | "dag")} className="flex min-h-0 flex-1 flex-col">
              <div className="flex items-center gap-3 border-b border-border bg-surface px-3 py-1.5">
                <TabsList>
                  <TabsTrigger value="graph" data-testid="tab-graph">
                    Knowledge Graph
                  </TabsTrigger>
                  <TabsTrigger value="dag" data-testid="tab-dag">
                    Execution DAG
                  </TabsTrigger>
                </TabsList>
                {doc && (
                  <span className="text-xs tabular-nums text-muted" data-testid="graph-stats">
                    {doc.nodes.length} nodes · {doc.edges.length} edges
                    {view === "dag" ? ` · DAG ${doc.dag.status}` : ""}
                  </span>
                )}
              </div>
              <FilterBar filters={filters} onChange={setFilters} />
              <TabsContent value="graph" className="flex min-h-0 flex-1 flex-col" data-testid="graph-area">
                {doc && kg ? (
                  <GraphCanvas view={kg} filters={filters} selection={selection} onSelect={select} dark={theme === "dark"} label="Knowledge graph" />
                ) : (
                  <div className="flex h-full items-center justify-center p-6 text-center text-sm text-muted" data-testid="graph-empty">
                    Press “Analyze Prompt” to build the graph from the text on the left.
                  </div>
                )}
              </TabsContent>
              <TabsContent value="dag" className="flex min-h-0 flex-1 flex-col" data-testid="dag-area">
                {doc && dag ? (
                  <>
                    <DagPanel doc={doc} onSelect={select} subgraph={subgraph} onToggleSubgraph={setSubgraph} />
                    <div className="min-h-0 flex-1">
                      {dag.nodes.length > 0 ? (
                        <GraphCanvas view={dag} filters={filters} selection={selection} onSelect={select} dark={theme === "dark"} label="Execution DAG" />
                      ) : (
                        <div className="flex h-full items-center justify-center p-6 text-sm text-muted">No tasks, so there is nothing to order.</div>
                      )}
                    </div>
                  </>
                ) : (
                  <div className="flex h-full items-center justify-center p-6 text-center text-sm text-muted">Analyze a prompt to see its execution order.</div>
                )}
              </TabsContent>
            </Tabs>
          </div>

          <div className={cn("min-h-0 grid-cols-1 border-t border-border sm:grid-cols-[minmax(200px,38%)_1fr] lg:h-[40%]", pane === "details" ? "grid h-full" : "hidden", "lg:grid")}>
            <Tabs value={bottom} onValueChange={(v) => setBottom(v as typeof bottom)} className="flex min-h-0 flex-col p-2">
              <TabsList className="self-start">
                <TabsTrigger value="nodes" data-testid="tab-nodes">
                  Nodes
                </TabsTrigger>
                <TabsTrigger value="diagnostics" data-testid="tab-diagnostics">
                  Diagnostics{doc ? ` ${counts.all}` : ""}
                  {counts.error > 0 && <span className="ml-1 text-err" aria-label={`${counts.error} errors`}>●</span>}
                </TabsTrigger>
                <TabsTrigger value="queries" data-testid="tab-queries">
                  Queries
                </TabsTrigger>
              </TabsList>
              <TabsContent value="nodes" className="mt-2 min-h-0 flex-1 overflow-hidden">
                <NodeList nodes={listed} selection={selection} onSelect={select} />
              </TabsContent>
              <TabsContent value="diagnostics" className="mt-2 min-h-0 flex-1 overflow-hidden">
                <DiagnosticsPanel diagnostics={doc?.diagnostics ?? []} activeId={focusDiag?.id ?? null} onPick={pickDiagnostic} />
              </TabsContent>
              <TabsContent value="queries" className="mt-2 min-h-0 flex-1 overflow-auto">
                <QueriesPanel graphId={doc?.graph_id ?? null} onPickRow={pickQueryRow} />
              </TabsContent>
            </Tabs>
            <div className="min-h-0 overflow-auto border-l border-border p-3" aria-live="polite">
              <Inspector doc={doc} selection={selection} onSelect={select} onFocusEvidence={(file, start) => goTo(file, start)} />
            </div>
          </div>
        </section>
      </main>
    </div>
  );
}
