"""GraphML via NetworkX. Nested values are stored as JSON text so any GraphML reader can load them.

XML 1.0 cannot carry some characters (controls, lone surrogates, U+FFFE/FFFF). They are replaced with
U+FFFD and the number of replacements is stored in the graph attribute ``xml_replaced_chars``, so the
loss is visible; graph.json keeps the original text.
"""

from __future__ import annotations

import io
import json

import networkx as nx

from ..ir import GraphDocument
from ..security import xml_safe, xml_unsafe_count


def to_graphml(doc: GraphDocument) -> str:
    replaced = 0

    def s(value: str) -> str:
        nonlocal replaced
        replaced += xml_unsafe_count(value)
        return xml_safe(value)

    def js(value: object) -> str:
        return s(json.dumps(value, sort_keys=True, ensure_ascii=False))

    g = nx.MultiDiGraph(
        graph_id=s(doc.graph_id), schema_version=s(doc.schema_version), analyzer_version=s(doc.analyzer_version)
    )
    for n in doc.nodes:
        g.add_node(
            s(n.id), type=n.type, label=s(n.label), description=s(n.description), original_text=s(n.original_text),
            source_file=s(n.source_file), span_start=n.source_span.start, span_end=n.source_span.end,
            role=s(n.role_scope.role or ""), agent=s(n.role_scope.agent or ""), confidence=float(n.confidence),
            extraction_method=n.extraction_method, validation_status=n.validation_status, metadata=js(n.metadata),
        )  # fmt: skip
    for e in doc.edges:
        g.add_edge(
            s(e.source), s(e.target), key=s(e.id), edge_id=s(e.id), relation=e.relation, status=e.status,
            rationale=s(e.rationale),
            reference=s(e.reference or ""), rule=s(e.rule or ""), confidence=float(e.confidence),
            evidence=js([ev.model_dump(mode="json") for ev in e.evidence]),
        )  # fmt: skip
    g.graph["xml_replaced_chars"] = replaced
    buf = io.BytesIO()
    nx.write_graphml(g, buf, encoding="utf-8", named_key_ids=True)
    return buf.getvalue().decode("utf-8")
