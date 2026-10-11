"""Parser vs. hand-written expectations. Nodes, edges and the list of uncovered text are compared as
exact sets; node/edge attributes named in the expectation must match. Diagnostics and DAG
expectations are checked in test_fixtures_analysis.py (milestone M3)."""

import pytest

from promptgraphify.analyze import analyze

from .fixture_loader import load_fixtures, resolve

FIXTURES = load_fixtures()
NEEDS_LATER = {
    "06_yaml_prompt": "YAML front-end is milestone M3",
    "07_json_messages": "JSON front-end is milestone M3",
}


def params():
    out = []
    for f in FIXTURES:
        marks = [pytest.mark.skip(reason=NEEDS_LATER[f.name])] if f.name in NEEDS_LATER else []
        out.append(pytest.param(f, id=f.name, marks=marks))
    return out


def ident(n_type, file, start, end):
    return (n_type, file, start, end)


@pytest.mark.parametrize("fx", params())
def test_nodes_edges_and_uncovered_match_the_expectation(fx):
    exp = resolve(fx)
    doc = analyze(fx.files)

    # ---- nodes: exact set of (type, file, span)
    want = {ident(n.type, n.loc.file, n.loc.span.start, n.loc.span.end): n for n in exp.nodes}
    got = {ident(n.type, n.source_file, n.source_span.start, n.source_span.end): n for n in doc.nodes}
    missing = sorted(want.keys() - got.keys())
    extra = sorted(got.keys() - want.keys())
    assert not missing, "missing nodes: " + "; ".join(f"{k[0]} {fx.files[k[1]][k[2] : k[3]]!r}" for k in missing)
    assert not extra, "unexpected nodes: " + "; ".join(f"{k[0]} {fx.files[k[1]][k[2] : k[3]]!r}" for k in extra)
    assert len(doc.nodes) == len(exp.nodes)

    key_to_id = {}
    for key, n in want.items():
        actual = got[key]
        key_to_id[n.key] = actual.id
        spec = n.spec
        if "role" in spec:
            assert actual.role_scope.role == spec["role"], f"{n.key}: role"
        if "agent" in spec:
            assert actual.role_scope.agent == spec["agent"], f"{n.key}: agent"
        for flag in ("declared", "defined", "produced"):
            if flag in spec:
                assert actual.metadata.get(flag) == spec[flag], f"{n.key}: {flag}"
        if "decoded" in spec:
            assert actual.decoded_text == spec["decoded"], f"{n.key}: decoded_text"
        if "span_precision" in spec:
            assert actual.metadata["span_precision"] == spec["span_precision"]
        if "id_suffix" in spec:
            assert actual.id.endswith(spec["id_suffix"]) if spec["id_suffix"] else "~" not in actual.id, (
                f"{n.key}: id {actual.id}"
            )
        if "id_contains" in spec:
            assert spec["id_contains"] in actual.id

    # ---- edges: exact set of (relation, source, target, status)
    want_edges = {(e.relation, key_to_id[e.source], key_to_id[e.target], e.status): e for e in exp.edges}
    got_edges = {}
    for e in doc.edges:
        got_edges.setdefault((e.relation, e.source, e.target, e.status), []).append(e)
    id_to_key = {v: k for k, v in key_to_id.items()}

    def show(k):
        return f"{k[0]} {id_to_key.get(k[1], k[1])} -> {id_to_key.get(k[2], k[2])} [{k[3]}]"

    assert not (want_edges.keys() - got_edges.keys()), "missing edges: " + "; ".join(
        show(k) for k in sorted(want_edges.keys() - got_edges.keys())
    )
    assert not (got_edges.keys() - want_edges.keys()), "unexpected edges: " + "; ".join(
        show(k) for k in sorted(got_edges.keys() - want_edges.keys())
    )
    for k, e in want_edges.items():
        actual = got_edges[k][0]
        assert len(got_edges[k]) == 1, f"{show(k)} produced {len(got_edges[k])} times"
        if e.status == "EXTRACTED":
            assert actual.reference == e.spec["reference"], f"{show(k)}: reference {actual.reference!r}"
        else:
            if "rule" in e.spec:
                assert actual.rule == e.spec["rule"], f"{show(k)}: rule {actual.rule!r}"
            if "reference" in e.spec:
                assert actual.reference == e.spec["reference"]
        for mk, mv in e.spec.get("metadata", {}).items():
            assert actual.metadata.get(mk) == mv, f"{show(k)}: metadata {mk}={actual.metadata.get(mk)!r}"
        for want_ev in e.evidence:
            assert any(
                a.source_file == want_ev.file and a.span.start <= want_ev.span.start and want_ev.span.end <= a.span.end
                for a in actual.evidence
            ), f"{show(k)}: evidence {want_ev.text!r} is not covered by the produced evidence"

    # ---- uncovered text is reported, exactly
    for c in doc.coverage:
        got_unc = sorted(fx.files[c.source_file][s.start : s.end] for s in c.uncovered_spans)
        want_unc = sorted(u.text for u in exp.uncovered if u.file == c.source_file)
        assert got_unc == want_unc, f"uncovered text in {c.source_file}"
