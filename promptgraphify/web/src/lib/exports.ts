export interface ExportOption {
  fmt: string;
  view: "graph" | "dag";
  label: string;
  hint: string;
}

// The formats of GET /api/graph/{id}/export/{format}; the server is the source of truth for what exists.
export const EXPORTS: ExportOption[] = [
  { fmt: "html", view: "graph", label: "graph.html", hint: "Interactive viewer; one file, works offline" },
  { fmt: "report", view: "graph", label: "GRAPH_REPORT.md", hint: "Readable summary with evidence" },
  { fmt: "json", view: "graph", label: "graph.json", hint: "The full graph document" },
  { fmt: "svg", view: "graph", label: "graph.svg", hint: "Knowledge graph picture" },
  { fmt: "svg", view: "dag", label: "graph-dag.svg", hint: "Execution DAG picture" },
  { fmt: "mermaid", view: "graph", label: "graph.mmd", hint: "Mermaid, knowledge graph" },
  { fmt: "mermaid", view: "dag", label: "graph-dag.mmd", hint: "Mermaid, execution DAG" },
  { fmt: "graphml", view: "graph", label: "graph.graphml", hint: "GraphML for Gephi / yEd" },
];

export function exportUrl(graphId: string, o: ExportOption): string {
  const view = o.view === "dag" ? "?view=dag" : "";
  return `/api/graph/${encodeURIComponent(graphId)}/export/${o.fmt}${view}`;
}
