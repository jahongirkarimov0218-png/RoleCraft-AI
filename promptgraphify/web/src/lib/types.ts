// Aliases over the types generated from the backend's OpenAPI document (src/lib/api-types.ts).
import type { components } from "./api-types";

type S = components["schemas"];
export type GraphDocument = S["GraphDocument"];
export type GraphNode = S["Node"];
export type GraphEdge = S["Edge"];
export type Diagnostic = S["Diagnostic"];
export type Evidence = S["Evidence"];
export type SourceCoverage = S["SourceCoverage"];
export type DagView = S["DagView"];
export type AnalyzeResponse = S["AnalyzeResponse"];
export type ErrorResponse = S["ErrorResponse"];
export type QueryResult = S["QueryResult"];
export type QuerySpec = S["QuerySpec"];
export type QueryRow = S["Row"];

export type NodeType = GraphNode["type"];
export type Relation = GraphEdge["relation"];
export type EdgeStatus = GraphEdge["status"];

export const NODE_TYPES: NodeType[] = [
  "SystemNode",
  "TaskNode",
  "ContextNode",
  "ConstraintNode",
  "ToolNode",
  "ExampleNode",
];
export const EDGE_STATUSES: EdgeStatus[] = ["EXTRACTED", "INFERRED", "AMBIGUOUS"];

export type Severity = Diagnostic["severity"];

export type Selection = { kind: "node"; id: string } | { kind: "edge"; id: string } | null;
