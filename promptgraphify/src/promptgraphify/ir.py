"""Intermediate representation: the one schema every layer, the CLI, the API and the exports share.

Models forbid unknown fields so a typo in a producer fails loudly. Cross-reference invariants (spans
match the source, relation endpoint types, EXTRACTED needs an explicit reference …) are checked by
``validate.py`` (Layer C), not here.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, field_validator

from .ontology import EdgeStatus, NodeType, Relation
from .spans import Span

SCHEMA_VERSION = "1.0"
CONFIDENCE_DIGITS = 4

MessageRole = Literal["system", "developer", "user", "assistant", "tool"]
Severity = Literal["error", "warning", "info"]
Certainty = Literal["proven", "probable"]
Detection = Literal["deterministic", "heuristic", "llm"]
ValidationStatus = Literal["unverified", "verified", "downgraded"]

# ``deterministic:<rule>`` or ``llm:<adapter>``; the rule name is what an INFERRED edge cites.
EXTRACTION_METHOD_PATTERN = r"^(deterministic|llm):[A-Za-z0-9_.\-]+$"


class _Model(BaseModel):
    """Every field is required (nullable ones included): producers state everything explicitly, and the
    generated OpenAPI / TypeScript types therefore have no optional fields to second-guess."""

    model_config = ConfigDict(extra="forbid")


class RoleScope(_Model):
    """Who speaks / which agent owns a unit. Replaces extra node types (ontology is closed)."""

    role: MessageRole | None
    agent: str | None


class Evidence(_Model):
    source_file: str
    span: Span
    text: str  # exact copy of source[span], kept so a consumer needs no second lookup


class _Scored(_Model):
    confidence: float = Field(gt=0, le=1)

    @field_validator("confidence")
    @classmethod
    def _round(cls, value: float) -> float:
        return round(value, CONFIDENCE_DIGITS)


class Node(_Scored):
    id: str
    type: NodeType
    label: str
    description: str
    original_text: str  # raw slice of the source: source[start:end] == original_text
    decoded_text: str | None  # escapes opened / indentation removed; never used for spans
    source_file: str
    source_span: Span
    role_scope: RoleScope
    metadata: dict[str, JsonValue]
    extraction_method: str = Field(pattern=EXTRACTION_METHOD_PATTERN)
    validation_status: ValidationStatus


class Edge(_Scored):
    id: str
    source: str
    target: str
    relation: Relation
    rationale: str
    evidence: list[Evidence]
    status: EdgeStatus
    # EXTRACTED: literal text inside one evidence span that makes the link explicit.
    reference: str | None
    # INFERRED: name of the deterministic rule (e.g. ``scope.section``) or of the LLM adapter.
    rule: str | None
    extraction_method: str = Field(pattern=EXTRACTION_METHOD_PATTERN)
    metadata: dict[str, JsonValue]


class Diagnostic(_Model):
    id: str
    rule_id: str
    severity: Severity
    certainty: Certainty
    detection: Detection
    description: str
    evidence: list[Evidence]
    affected_nodes: list[str]
    affected_edges: list[str]
    suggested_fix: str


class SourceFile(_Model):
    path: str
    text: str
    sha256: str
    length: int  # code points
    has_bom: bool
    newline: Literal["none", "lf", "crlf", "cr", "mixed"]


class SourceCoverage(_Model):
    """Partition of the non-whitespace code points of one source (ANALYSIS_SPEC §2)."""

    source_file: str
    total: int
    covered: int
    structural: int
    uncovered: int
    structural_spans: list[Span]
    uncovered_spans: list[Span]

    @property
    def ratio(self) -> float:
        return 1.0 if self.total == 0 else round((self.covered + self.structural) / self.total, 4)


class DagEdge(_Model):
    source: str
    target: str
    relation: Relation
    graph_edge: str  # id of the knowledge-graph edge this arrow was projected from
    conditional: bool
    condition: str | None
    loop: bool


class UnresolvedDependency(_Model):
    node_id: str
    reference: str
    evidence: Evidence


class CycleReport(_Model):
    nodes: list[str]
    edges: list[str]
    evidence: list[Evidence]
    certainty: Certainty


class MetricValue(_Model):
    name: str
    value: JsonValue
    definition: str  # graph-theoretic definition shown with every derived number


class DagView(_Model):
    status: Literal["ok", "blocked", "empty"]
    vertices: list[str]
    edges: list[DagEdge]
    topological_order: list[str]
    critical_path: list[str]
    unresolved: list[UnresolvedDependency]
    cycles: list[CycleReport]
    acyclic_subgraph: list[DagEdge] | None
    removed_for_acyclic: list[str]  # edge ids dropped, never silent
    loops: list[str]
    metrics: list[MetricValue]


class ToolInfo(_Model):
    name: str = "promptgraphify"
    version: str


class AnalysisConfig(_Model):
    layer_b: bool  # optional LLM extraction; off by default


class GraphDocument(_Model):
    """The content of graph.json. No timestamps or host data: same input -> same bytes."""

    schema_version: str
    tool: ToolInfo
    analyzer_version: str
    graph_id: str
    config: AnalysisConfig
    sources: list[SourceFile]
    nodes: list[Node]
    edges: list[Edge]
    diagnostics: list[Diagnostic]
    coverage: list[SourceCoverage]
    dag: DagView
    warnings: list[str]

    def node_by_id(self) -> dict[str, Node]:
        return {n.id: n for n in self.nodes}


def empty_dag() -> DagView:
    return DagView(
        status="empty", vertices=[], edges=[], topological_order=[], critical_path=[], unresolved=[],
        cycles=[], acyclic_subgraph=None, removed_for_acyclic=[], loops=[], metrics=[],
    )  # fmt: skip
