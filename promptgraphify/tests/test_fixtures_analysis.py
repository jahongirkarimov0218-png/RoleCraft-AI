"""Diagnostics and Execution DAG against the hand-written expectations (non-exhaustive for diagnostics:
listed ones must appear with exactly the stated node set; `absent_rules` must not fire)."""

import pytest

from promptgraphify.analyze import analyze
from promptgraphify.rules import RULES

from .fixture_loader import load_fixtures, locate, resolve

FIXTURES = load_fixtures()


def key_ids(fx, doc):
    exp = resolve(fx)
    got = {(n.type, n.source_file, n.source_span.start, n.source_span.end): n.id for n in doc.nodes}
    return {n.key: got[(n.type, n.loc.file, n.loc.span.start, n.loc.span.end)] for n in exp.nodes}


@pytest.mark.parametrize("fx", FIXTURES, ids=lambda f: f.name)
def test_diagnostics_match_expectations(fx):
    doc = analyze(fx.files)
    ids = key_ids(fx, doc)
    produced = list(doc.diagnostics)
    for want in fx.expected["diagnostics"]:
        wanted_nodes = {ids[k] for k in want["nodes"]}
        match = next(
            (
                d
                for d in produced
                if d.rule_id == want["rule_id"]
                and d.certainty == want["certainty"]
                and set(d.affected_nodes) == wanted_nodes
                and _evidence_ok(fx, d, want)
            ),
            None,
        )
        assert match is not None, (
            f"expected {want['rule_id']} ({want['certainty']}) on {sorted(want['nodes'])}; produced: "
            + ", ".join(f"{d.rule_id}/{d.certainty}/{sorted(d.affected_nodes)}" for d in produced)
        )
        produced.remove(match)  # each expected diagnostic consumes one produced diagnostic
    fired = {d.rule_id for d in doc.diagnostics}
    for rule in fx.expected["absent_rules"]:
        assert rule not in fired, f"{rule} fired but must not: " + "; ".join(
            d.description for d in doc.diagnostics if d.rule_id == rule
        )


def _evidence_ok(fx, d, want) -> bool:
    for ev in want.get("evidence", []):
        spec = {"quote": ev} if isinstance(ev, str) else ev
        loc = locate(fx, spec["quote"], spec.get("occurrence"), spec.get("file"))
        if not any(
            a.source_file == loc.file and a.span.start <= loc.span.start and loc.span.end <= a.span.end
            for a in d.evidence
        ):
            return False
    return True


@pytest.mark.parametrize("fx", [f for f in FIXTURES if "dag" in f.expected], ids=lambda f: f.name)
def test_dag_matches_expectations(fx):
    doc = analyze(fx.files)
    ids = key_ids(fx, doc)
    want = fx.expected["dag"]
    assert doc.dag.status == want["status"]
    if "topological_order" in want:
        assert doc.dag.topological_order == [ids[k] for k in want["topological_order"]]
    if "critical_path" in want:
        assert doc.dag.critical_path == [ids[k] for k in want["critical_path"]]
    if "cycle_nodes" in want:
        assert {n for c in doc.dag.cycles for n in c.nodes} == {ids[k] for k in want["cycle_nodes"]}
        assert (
            doc.dag.topological_order == [] and doc.dag.critical_path == []
        )  # a blocked DAG is not presented as valid
    if "loops" in want:
        assert len(doc.dag.loops) == want["loops"]


def test_every_listed_rule_is_implemented_or_declared_unfinished():
    from promptgraphify.analyzer import implemented_rules

    assert set(RULES) == implemented_rules()
