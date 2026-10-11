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
    model_config = ConfigDict(extra="forbid")


class RoleScope(_Model):
    """Who speaks / which agent owns a unit. Replaces extra node types (ontology is closed)."""

    role: MessageRole | None = None
    agent: str | None = None


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
    decoded_text: str | None = None  # escapes opened / indentation removed; never used for spans
    source_file: str
    source_span: Span
    role_scope: RoleScope = Field(default_factory=RoleScope)
    metadata: dict[str, JsonValue] = Field(default_factory=dict)
    extraction_method: str = Field(pattern=EXTRACTION_METHOD_PATTERN)
    validation_status: ValidationStatus = "unverified"


class Edge(_Scored):
    id: str
    source: str
    target: str
    relation: Relation
    rationale: str
    evidence: list[Evidence]
    status: EdgeStatus
    # EXTRACTED: literal text inside one evidence span that makes the link explicit.
    reference: str | None = None
    # INFERRED: name of the deterministic rule (e.g. ``scope.section``) or of the LLM adapter.
    rule: str | None = None
    extraction_method: str = Field(pattern=EXTRACTION_METHOD_PATTERN)
    metadata: dict[str, JsonValue] = Field(default_factory=dict)


class Diagnostic(_Model):
    id: str
    rule_id: str
    severity: Severity
    certainty: Certainty
    detection: Detection
    description: str
    evidence: list[Evidence] = Field(default_factory=list)
    affected_nodes: list[str] = Field(default_factory=list)
    affected_edges: list[str] = Field(default_factory=list)
    suggested_fix: str


class SourceFile(_Model):
    path: str
    text: str
    sha256: str
    length: int  # code points
    has_bom: bool = False
    newline: Literal["none", "lf", "crlf", "cr", "mixed"] = "none"


class SourceCoverage(_Model):
    """Partition of the non-whitespace code points of one source (ANALYSIS_SPEC §2)."""

    source_file: str
    total: int
    covered: int
    structural: int
    uncovered: int
    structural_spans: list[Span] = Field(default_factory=list)
    uncovered_spans: list[Span] = Field(default_factory=list)

    @property
    def ratio(self) -> float:
        return 1.0 if self.total == 0 else round((self.covered + self.structural) / self.total, 4)


class DagEdge(_Model):
    source: str
    target: str
    relation: Relation
    graph_edge: str  # id of the knowledge-graph edge this arrow was projected from
    conditional: bool = False
    condition: str | None = None
    loop: bool = False


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
    status: Literal["ok", "blocked", "empty"] = "empty"
    vertices: list[str] = Field(default_factory=list)
    edges: list[DagEdge] = Field(default_factory=list)
    topological_order: list[str] = Field(default_factory=list)
    critical_path: list[str] = Field(default_factory=list)
    unresolved: list[UnresolvedDependency] = Field(default_factory=list)
    cycles: list[CycleReport] = Field(default_factory=list)
    acyclic_subgraph: list[DagEdge] | None = None
    removed_for_acyclic: list[str] = Field(default_factory=list)  # edge ids dropped, never silent
    loops: list[str] = Field(default_factory=list)
    metrics: list[MetricValue] = Field(default_factory=list)


class ToolInfo(_Model):
    name: str = "promptgraphify"
    version: str


class AnalysisConfig(_Model):
    layer_b: bool = False  # optional LLM extraction; off by default
    max_input_chars: int = 500_000


class GraphDocument(_Model):
    """The content of graph.json. No timestamps or host data: same input -> same bytes."""

    schema_version: str = SCHEMA_VERSION
    tool: ToolInfo
    analyzer_version: str
    graph_id: str
    config: AnalysisConfig = Field(default_factory=AnalysisConfig)
    sources: list[SourceFile]
    nodes: list[Node] = Field(default_factory=list)
    edges: list[Edge] = Field(default_factory=list)
    diagnostics: list[Diagnostic] = Field(default_factory=list)
    coverage: list[SourceCoverage] = Field(default_factory=list)
    dag: DagView = Field(default_factory=DagView)
    warnings: list[str] = Field(default_factory=list)

    def node_by_id(self) -> dict[str, Node]:
        return {n.id: n for n in self.nodes}
