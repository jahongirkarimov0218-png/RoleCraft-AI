# ruff: noqa: E501
"""Compare two analyses of (versions of) one prompt.

Matching is by stable node ID first. Nodes left over on both sides are paired by text similarity only as
a *suggestion*: such a pair is reported as ``probably_modified`` with its similarity, never as a fact.
Six kinds of change are reported: nodes added/removed, dependencies added/removed, constraints changed,
execution sequence changed, diagnostics that appeared, diagnostics that were resolved.
"""

from __future__ import annotations

import difflib
from typing import Literal

from pydantic import BaseModel, ConfigDict

from .ids import normalize_text
from .ir import Diagnostic, Edge, Evidence, GraphDocument, Node
from .queries import EdgeRef, NodeRef, node_ref

SIMILARITY_THRESHOLD = 0.6
DEPENDENCY_RELATIONS = ("DEPENDS_ON", "PROVIDES_CONTEXT", "CALLS_TOOL", "CONDITIONALLY_EXECUTES")


class _M(BaseModel):
    model_config = ConfigDict(extra="forbid")


class NodePair(_M):
    old: NodeRef
    new: NodeRef
    similarity: float
    identical_text: bool  # same normalised text, different ID: the unit moved to another section
    basis: Literal["text_similarity"]  # a guess, labelled as such


class EdgeChange(_M):
    kind: Literal["added", "removed"]
    edge: EdgeRef
    source_label: str
    target_label: str
    evidence: list[Evidence]


class ConstraintChange(_M):
    kind: Literal["added", "removed", "probably_modified", "moved", "scope_changed"]
    constraint: NodeRef
    previous: NodeRef | None
    similarity: float | None
    detail: str


class OrderMove(_M):
    node: NodeRef
    old_index: int
    new_index: int


class SequenceChange(_M):
    changed: bool
    old_status: str
    new_status: str
    old_order: list[str]
    new_order: list[str]
    moved: list[OrderMove]
    old_critical_path: list[str]
    new_critical_path: list[str]
    note: str


class DiagnosticChange(_M):
    diagnostic: Diagnostic
    labels: list[str]


class DiffSummary(_M):
    nodes_added: int
    nodes_removed: int
    probably_modified: int
    dependencies_added: int
    dependencies_removed: int
    constraints_changed: int
    sequence_changed: bool
    diagnostics_new: int
    diagnostics_resolved: int


class DiffResult(_M):
    old_graph_id: str
    new_graph_id: str
    identical: bool
    summary: DiffSummary
    nodes_added: list[NodeRef]
    nodes_removed: list[NodeRef]
    probably_modified: list[NodePair]
    dependencies: list[EdgeChange]
    constraints: list[ConstraintChange]
    sequence: SequenceChange
    diagnostics_new: list[DiagnosticChange]
    diagnostics_resolved: list[DiagnosticChange]


def _text(n: Node) -> str:
    return normalize_text(n.decoded_text or n.original_text)


def _pair_by_similarity(old: list[Node], new: list[Node]) -> list[tuple[Node, Node, float]]:
    """Greedy one-to-one pairing of same-type leftovers, best similarity first; deterministic ties."""
    candidates = []
    for o in old:
        for n in new:
            if o.type != n.type:
                continue
            ratio = difflib.SequenceMatcher(None, _text(o), _text(n), autojunk=False).ratio()
            if ratio >= SIMILARITY_THRESHOLD:
                candidates.append((-ratio, o.id, n.id, o, n, ratio))
    candidates.sort(key=lambda c: c[:3])
    used_o: set[str] = set()
    used_n: set[str] = set()
    pairs = []
    for _, _, _, o, n, ratio in candidates:
        if o.id in used_o or n.id in used_n:
            continue
        used_o.add(o.id)
        used_n.add(n.id)
        pairs.append((o, n, round(ratio, 4)))
    return pairs


def _edge_key(e: Edge, remap: dict[str, str]) -> tuple[str, str, str]:
    return (e.relation, remap.get(e.source, e.source), remap.get(e.target, e.target))


def _diag_key(d: Diagnostic, nodes: dict[str, Node], remap: dict[str, str]) -> tuple:
    ids = tuple(sorted(remap.get(n, n) for n in d.affected_nodes))
    if ids:
        return (d.rule_id, ids)
    return (d.rule_id, (), tuple(sorted(normalize_text(e.text) for e in d.evidence)))


def _labels(d: Diagnostic, nodes: dict[str, Node]) -> list[str]:
    return [nodes[n].label for n in d.affected_nodes if n in nodes]


def diff_documents(old: GraphDocument, new: GraphDocument) -> DiffResult:
    onodes, nnodes = {n.id: n for n in old.nodes}, {n.id: n for n in new.nodes}
    only_old = sorted(
        (n for i, n in onodes.items() if i not in nnodes), key=lambda n: (n.source_file, n.source_span.start)
    )
    only_new = sorted(
        (n for i, n in nnodes.items() if i not in onodes), key=lambda n: (n.source_file, n.source_span.start)
    )
    pairs = _pair_by_similarity(only_old, only_new)
    remap = {o.id: n.id for o, n, _ in pairs}  # old id -> new id for probably-modified pairs
    paired_old = {o.id for o, _, _ in pairs}
    paired_new = {n.id for _, n, _ in pairs}
    added = [n for n in only_new if n.id not in paired_new]
    removed = [n for n in only_old if n.id not in paired_old]

    # --- dependencies (explicit graph relations that say "needs / uses / is gated by")
    oedges = {_edge_key(e, remap): e for e in old.edges if e.relation in DEPENDENCY_RELATIONS}
    nedges = {_edge_key(e, {}): e for e in new.edges if e.relation in DEPENDENCY_RELATIONS}
    changes: list[EdgeChange] = []

    def label_of(doc_nodes: dict[str, Node], nid: str) -> str:
        return doc_nodes[nid].label if nid in doc_nodes else nid

    for key in sorted(nedges.keys() - oedges.keys()):
        e = nedges[key]
        changes.append(
            EdgeChange(
                kind="added",
                edge=_eref(e),
                source_label=label_of(nnodes, e.source),
                target_label=label_of(nnodes, e.target),
                evidence=e.evidence,
            )
        )
    for key in sorted(oedges.keys() - nedges.keys()):
        e = oedges[key]
        changes.append(
            EdgeChange(
                kind="removed",
                edge=_eref(e),
                source_label=label_of(onodes, e.source),
                target_label=label_of(onodes, e.target),
                evidence=e.evidence,
            )
        )

    # --- constraints
    cons: list[ConstraintChange] = []
    for n in added:
        if n.type == "ConstraintNode":
            cons.append(
                ConstraintChange(
                    kind="added", constraint=node_ref(n), previous=None, similarity=None, detail="new constraint"
                )
            )
    for n in removed:
        if n.type == "ConstraintNode":
            cons.append(
                ConstraintChange(
                    kind="removed",
                    constraint=node_ref(n),
                    previous=None,
                    similarity=None,
                    detail="constraint no longer present",
                )
            )
    for o, n, ratio in pairs:
        if n.type == "ConstraintNode":
            same = _text(o) == _text(n)
            cons.append(
                ConstraintChange(
                    kind="moved" if same else "probably_modified",
                    constraint=node_ref(n),
                    previous=node_ref(o),
                    similarity=ratio,
                    detail="same wording in another section"
                    if same
                    else "similar constraint with different wording (a guess, not a fact)",
                )
            )
    for nid in sorted(onodes.keys() & nnodes.keys()):
        o, n = onodes[nid], nnodes[nid]
        if n.type == "ConstraintNode" and o.metadata.get("scope") != n.metadata.get("scope"):
            cons.append(
                ConstraintChange(
                    kind="scope_changed",
                    constraint=node_ref(n),
                    previous=node_ref(o),
                    similarity=None,
                    detail=f"scope {o.metadata.get('scope')!r} -> {n.metadata.get('scope')!r}",
                )
            )
    o_cons = {(_edge_key(e, remap)) for e in old.edges if e.relation == "CONSTRAINS"}
    n_cons = {(_edge_key(e, {})) for e in new.edges if e.relation == "CONSTRAINS"}
    for key in sorted(n_cons - o_cons):
        c = nnodes.get(key[1])
        if c is not None and c.id in nnodes and not any(x.constraint.id == c.id for x in cons):
            cons.append(
                ConstraintChange(
                    kind="scope_changed",
                    constraint=node_ref(c),
                    previous=None,
                    similarity=None,
                    detail=f"now constrains {label_of(nnodes, key[2])}",
                )
            )

    # --- execution sequence: relative order of the vertices both DAGs share
    common = [v for v in old.dag.topological_order if remap.get(v, v) in new.dag.topological_order]
    old_pos = {remap.get(v, v): i for i, v in enumerate(old.dag.topological_order)}
    new_pos = {v: i for i, v in enumerate(new.dag.topological_order)}
    shared = [remap.get(v, v) for v in common]
    old_rank = {v: i for i, v in enumerate(shared)}
    new_rank = {v: i for i, v in enumerate(sorted(shared, key=lambda v: new_pos[v]))}
    moved = [
        OrderMove(node=node_ref(nnodes[v]), old_index=old_pos[v], new_index=new_pos[v])
        for v in shared
        if old_rank[v] != new_rank[v]
    ]
    old_order = [onodes[v].label for v in old.dag.topological_order if v in onodes]
    new_order = [nnodes[v].label for v in new.dag.topological_order if v in nnodes]
    crit_o = [onodes[v].label for v in old.dag.critical_path if v in onodes]
    crit_n = [nnodes[v].label for v in new.dag.critical_path if v in nnodes]
    status_changed = old.dag.status != new.dag.status
    # compare vertices, not labels: a reworded step is the same vertex ("probably modified"), not a new order
    crit_changed = [remap.get(v, v) for v in old.dag.critical_path] != list(new.dag.critical_path)
    order_changed = bool(moved) or crit_changed
    note = (
        f"execution DAG changed from {old.dag.status} to {new.dag.status}"
        if status_changed
        else "relative order of shared vertices changed"
        if moved
        else "critical path changed"
        if order_changed
        else "order unchanged"
    )
    seq = SequenceChange(
        changed=bool(status_changed or order_changed), old_status=old.dag.status, new_status=new.dag.status,
        old_order=old_order, new_order=new_order, moved=moved, old_critical_path=crit_o, new_critical_path=crit_n, note=note,
    )  # fmt: skip

    # --- diagnostics
    okeys = {_diag_key(d, onodes, remap): d for d in old.diagnostics}
    nkeys = {_diag_key(d, nnodes, {}): d for d in new.diagnostics}
    d_new = [
        DiagnosticChange(diagnostic=nkeys[k], labels=_labels(nkeys[k], nnodes))
        for k in sorted(nkeys.keys() - okeys.keys(), key=repr)
    ]
    d_gone = [
        DiagnosticChange(diagnostic=okeys[k], labels=_labels(okeys[k], onodes))
        for k in sorted(okeys.keys() - nkeys.keys(), key=repr)
    ]

    summary = DiffSummary(
        nodes_added=len(added), nodes_removed=len(removed), probably_modified=len(pairs),
        dependencies_added=sum(c.kind == "added" for c in changes), dependencies_removed=sum(c.kind == "removed" for c in changes),
        constraints_changed=len(cons), sequence_changed=seq.changed, diagnostics_new=len(d_new), diagnostics_resolved=len(d_gone),
    )  # fmt: skip
    identical = (
        not added
        and not removed
        and not pairs
        and not changes
        and not cons
        and not seq.changed
        and not d_new
        and not d_gone
    )
    return DiffResult(
        old_graph_id=old.graph_id, new_graph_id=new.graph_id, identical=identical, summary=summary,
        nodes_added=[node_ref(n) for n in added], nodes_removed=[node_ref(n) for n in removed],
        probably_modified=[NodePair(old=node_ref(o), new=node_ref(n), similarity=r, identical_text=_text(o) == _text(n), basis="text_similarity") for o, n, r in pairs],
        dependencies=changes, constraints=cons, sequence=seq, diagnostics_new=d_new, diagnostics_resolved=d_gone,
    )  # fmt: skip


def _eref(e: Edge) -> EdgeRef:
    return EdgeRef(
        id=e.id, relation=e.relation, status=e.status, source=e.source, target=e.target, rationale=e.rationale
    )
