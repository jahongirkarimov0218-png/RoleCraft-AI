"""Checks that the hand-written fixture expectations are valid, internally consistent and agree with
docs/ANALYSIS_SPEC.md. These tests do not run any parser; they guard the *expectations*."""

import re
from pathlib import Path

import pytest

from promptgraphify.ontology import EDGE_STATUSES, NODE_TYPES, RELATION_TABLE, RELATIONS, pair_allowed
from promptgraphify.rules import RULES

from .dag_model import analyse
from .fixture_loader import QuoteError, load_fixtures, resolve

FIXTURES = load_fixtures()
IDS = [f.name for f in FIXTURES]
SPEC = (Path(__file__).parent.parent / "docs" / "ANALYSIS_SPEC.md").read_text(encoding="utf-8")

REQUIRED_TOPICS = {
    "simple_system_task", "multiple_dependencies", "multiple_agents", "nested_xml", "markdown_instructions",
    "yaml", "json", "few_shot", "tool_schema", "missing_variable", "contradictory_constraints",
    "cyclic_dependency", "ambiguous_instruction", "prompt_injection", "uzbek", "russian",
    "malformed_xml", "loop", "crlf_bom_non_bmp", "empty_input", "nested_templates", "directory",
}  # fmt: skip


def test_at_least_twenty_fixtures():
    assert len(FIXTURES) >= 20


def test_required_topics_languages_types_relations_statuses_are_covered():
    topics = {t for f in FIXTURES for t in f.expected.get("topics", [])}
    assert REQUIRED_TOPICS <= topics, REQUIRED_TOPICS - topics
    langs = {part for f in FIXTURES for part in f.expected["language"].split("+")}
    assert {"en", "uz", "ru"} <= langs
    resolved = [resolve(f) for f in FIXTURES]
    assert {n.type for r in resolved for n in r.nodes} == set(NODE_TYPES)
    assert {e.relation for r in resolved for e in r.edges} == set(RELATIONS)
    assert {e.status for r in resolved for e in r.edges} == set(EDGE_STATUSES)


@pytest.mark.parametrize("fx", FIXTURES, ids=IDS)
def test_expectation_is_wellformed(fx):
    exp = fx.expected
    assert exp["review_status"].startswith("unreviewed"), (
        "labels written by the author are never 'human-reviewed'"
    )
    assert fx.files, "fixture has no input"
    res = resolve(fx)  # raises QuoteError on missing / ambiguous quotes

    # nodes
    seen = set()
    for n in res.nodes:
        assert n.type in NODE_TYPES
        assert len(n.loc.span) > 0
        ident = (n.type, n.loc.file, n.loc.span.start, n.loc.span.end)
        assert ident not in seen, f"two expected nodes with the same type and span: {n.key}"
        seen.add(ident)
    keys = {n.key: n for n in res.nodes}
    assert not (set(exp.get("absent_types", [])) & {n.type for n in res.nodes})

    # edges
    triples = set()
    for e in res.edges:
        assert e.source in keys and e.target in keys, f"dangling edge {e.relation} {e.source}->{e.target}"
        assert pair_allowed(e.relation, keys[e.source].type, keys[e.target].type), (
            f"{e.relation} {keys[e.source].type}->{keys[e.target].type} violates the relation table"
        )
        assert e.status in RELATION_TABLE[e.relation].allowed_status
        assert e.evidence, "every edge needs evidence"
        marker = (e.relation, e.source, e.target, tuple((x.file, x.span.start) for x in e.evidence))
        assert marker not in triples, f"duplicate expected edge {marker[:3]}"
        triples.add(marker)
        meta = e.spec.get("metadata", {})
        if e.source == e.target:
            assert meta.get("loop") or meta.get("self_reference"), "self-loop must be marked"
        if e.status == "EXTRACTED":
            ref = e.spec.get("reference")
            assert ref, f"EXTRACTED {e.relation} {e.source}->{e.target} has no explicit reference"
            assert any(ref in x.text for x in e.evidence), f"reference {ref!r} not inside its evidence"
        if e.status == "INFERRED":
            assert e.spec.get("rule"), "INFERRED edge must name its rule"
        if RELATION_TABLE[e.relation].symmetric:
            a, b = keys[e.source].loc, keys[e.target].loc
            assert (a.file, a.span.start) <= (b.file, b.span.start), (
                "symmetric edge must start at the earlier span"
            )

    # diagnostics
    for d in exp.get("diagnostics", []):
        rule = RULES[d["rule_id"]]
        if rule.certainty in ("proven", "probable"):
            assert d["certainty"] == rule.certainty, f"{d['rule_id']} must be {rule.certainty}"
        assert set(d["nodes"]) <= set(keys)
        for ev in d.get("evidence", []):
            from .fixture_loader import locate

            item = {"quote": ev} if isinstance(ev, str) else ev
            locate(fx, item["quote"], item.get("occurrence"), item.get("file"))
    fired = {d["rule_id"] for d in exp.get("diagnostics", [])}
    assert not (fired & set(exp.get("absent_rules", []))), "a rule is both expected and forbidden"
    assert set(exp.get("absent_rules", [])) <= set(RULES), "absent_rules names an unknown rule"

    # uncovered text must not overlap any expected node
    for u in res.uncovered:
        for n in res.nodes:
            if u.file == n.loc.file:
                assert not u.span.overlaps(n.loc.span), f"uncovered {u.text!r} overlaps node {n.key}"

    # byte-level claims are real
    claims = exp.get("bytes")
    if claims:
        raw = next(iter(fx.raw.values()))
        assert claims["bom"] == raw.startswith(b"\xef\xbb\xbf")
        assert claims["crlf"] == (b"\r\n" in raw)
        assert claims["non_bmp"] == any(ord(c) > 0xFFFF for c in raw.decode("utf-8"))


@pytest.mark.parametrize("fx", [f for f in FIXTURES if "dag" in f.expected], ids=lambda f: f.name)
def test_hand_written_dag_expectations_agree_with_the_spec_projection(fx):
    expected = fx.expected["dag"]
    got = analyse(resolve(fx))
    assert got["status"] == expected["status"]
    for field in ("topological_order", "critical_path", "cycle_nodes", "loops"):
        if field in expected:
            assert got[field] == expected[field], field


def test_quote_errors_are_loud():
    fx = FIXTURES[0]
    from .fixture_loader import locate

    with pytest.raises(QuoteError):
        locate(fx, "this text is not in the fixture")
    with pytest.raises(QuoteError):
        locate(fx, "e")  # occurs many times, no occurrence given


def test_rules_registry_matches_the_spec_table():
    section = SPEC[SPEC.index("## 7. Diagnostics") : SPEC.index("## 8. Node IDs")]
    rows = re.findall(r"^\| `([a-z_.]+)` \|.*?\| (D|H) \| (\w+)", section, flags=re.M)
    documented = {rid: (det, cert) for rid, det, cert in rows}
    assert set(documented) == set(RULES), set(documented) ^ set(RULES)
    for rid, (det, cert) in documented.items():
        rule = RULES[rid]
        assert (det == "D") == (rule.detection == "deterministic"), rid
        assert cert == ("proven" if rule.certainty in ("proven", "mixed") else "probable"), rid
