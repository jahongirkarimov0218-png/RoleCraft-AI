"""Graph endpoints: stored graphs, node details, shortest path, named queries, validate."""

import pytest
from fastapi.testclient import TestClient

from promptgraphify.api.app import Settings, create_app
from promptgraphify.api.schemas import ErrorResponse, NodeDetail, ValidateResponse
from promptgraphify.ir import GraphDocument
from promptgraphify.queries import QueryResult
from promptgraphify.storage import SqliteGraphStore

PROMPT = (
    "# Pipeline\n## Agent: A\nYou are agent A.\n1. Extract {{x}}.\n2. Check step 1.\n3. Pass the result to B.\n"
    "## Agent: B\nCall the lookup_user tool.\nNever lie.\n"
)


@pytest.fixture()
def client():
    return TestClient(create_app(Settings(), SqliteGraphStore(":memory:")))


@pytest.fixture()
def gid(client):
    r = client.post("/api/analyze", json={"files": [{"path": "p.md", "text": PROMPT}]})
    assert r.status_code == 200
    return r.json()["graph_id"]


def test_analyze_persists_the_graph_under_its_id(client, gid):
    r = client.get(f"/api/graph/{gid}")
    assert r.status_code == 200
    doc = GraphDocument.model_validate(r.json())
    assert doc.graph_id == gid and doc.dag.status in ("ok", "blocked")


def test_same_input_same_id_and_the_second_save_is_a_noop(client, gid):
    again = client.post("/api/analyze", json={"files": [{"path": "p.md", "text": PROMPT}]}).json()["graph_id"]
    assert again == gid


@pytest.mark.parametrize("bad", ["nope", "0123456789abcdeg", "0" * 16, "A" * 16, "../etc"])
def test_unknown_or_malformed_ids_are_404_in_the_error_envelope(client, bad):
    for url in (f"/api/graph/{bad}", f"/api/graph/{bad}/path?source=a&target=b", f"/api/graph/{bad}/query/conflicts"):
        r = client.get(url)
        assert r.status_code == 404, url
        assert ErrorResponse.model_validate(r.json()).error.code == "not_found"


def test_node_detail_has_edges_and_diagnostics(client, gid):
    doc = GraphDocument.model_validate(client.get(f"/api/graph/{gid}").json())
    tool = next(n for n in doc.nodes if n.type == "ToolNode")
    r = client.get(f"/api/graph/{gid}/node/{tool.id}")  # ids contain ':' and '~' and must survive the URL
    assert r.status_code == 200
    detail = NodeDetail.model_validate(r.json())
    assert detail.node.id == tool.id and [e.relation for e in detail.incoming] == ["CALLS_TOOL"]
    assert any(d.rule_id == "tool.undefined" for d in detail.diagnostics)
    assert client.get(f"/api/graph/{gid}/node/task:nope:x").status_code == 404


def test_path_endpoint_is_the_shortest_path_query(client, gid):
    r = client.get(f"/api/graph/{gid}/path", params={"source": "Pass the result", "target": "lookup_user"})
    assert r.status_code == 200
    res = QueryResult.model_validate(r.json())
    assert res.status == "ok" and res.paths and len(res.paths[0]) == 3  # pass -> call -> lookup_user
    back = QueryResult.model_validate(
        client.get(f"/api/graph/{gid}/path", params={"source": "lookup_user", "target": "Pass the result"}).json()
    )
    assert back.status == "no_path"
    und = QueryResult.model_validate(
        client.get(
            f"/api/graph/{gid}/path",
            params={"source": "lookup_user", "target": "Pass the result", "undirected": "true"},
        ).json()
    )
    assert und.status == "ok"
    assert client.get(f"/api/graph/{gid}/path", params={"source": "x"}).status_code == 422


def test_named_queries_over_http(client, gid):
    specs = client.get("/api/queries").json()
    assert len(specs) == 8
    r = client.get(f"/api/graph/{gid}/query/agent_tools")
    res = QueryResult.model_validate(r.json())
    assert res.rows and res.rows[0].title == "B"
    assert (
        client.get(f"/api/graph/{gid}/query/task_context", params={"task": "Extract"}).json()["rows"][0]["title"] == "x"
    )
    assert client.get(f"/api/graph/{gid}/query/nope").status_code == 404
    ambiguous = client.get(f"/api/graph/{gid}/query/task_context", params={"task": "the"}).json()
    assert ambiguous["status"] in ("ambiguous", "not_found")


def test_validate_files_reports_diagnostics_and_ok_flag(client):
    bad = client.post(
        "/api/validate", json={"files": [{"path": "p.md", "text": "1. Check step 2.\n2. Check step 1.\n"}]}
    )
    res = ValidateResponse.model_validate(bad.json())
    assert res.ok is False and res.counts.error >= 1 and any(d.rule_id == "dependency.cycle" for d in res.diagnostics)
    good = ValidateResponse.model_validate(
        client.post("/api/validate", json={"files": [{"path": "p.md", "text": "Never lie.\n"}]}).json()
    )
    assert good.ok is True and good.counts.error == 0


def test_validate_graph_document_detects_tampering(client, gid):
    doc = client.get(f"/api/graph/{gid}").json()
    ok = ValidateResponse.model_validate(client.post("/api/validate", json={"graph": doc}).json())
    assert ok.violations == []
    doc["nodes"][0]["original_text"] = "tampered text"
    tampered = ValidateResponse.model_validate(client.post("/api/validate", json={"graph": doc}).json())
    assert tampered.ok is False and any(v.code == "node.span_mismatch" for v in tampered.violations)


def test_validate_needs_exactly_one_input(client):
    assert client.post("/api/validate", json={}).status_code == 422
    assert client.post("/api/validate", json={"files": [{"path": "p", "text": "x"}], "graph": {}}).status_code == 422


def test_a_graph_with_a_foreign_schema_version_is_refused_clearly(client):
    doc = client.post("/api/analyze", json={"files": [{"path": "p.md", "text": "Never lie.\n"}]}).json()["graph"]
    doc["schema_version"] = "0.9"
    res = ValidateResponse.model_validate(client.post("/api/validate", json={"graph": doc}).json())
    assert res.ok is False and res.violations[0].code == "schema.version"


def test_openapi_lists_every_endpoint(client):
    paths = set(client.get("/openapi.json").json()["paths"])
    assert {
        "/api/analyze", "/api/validate", "/api/graph/{graph_id}", "/api/graph/{graph_id}/node/{node_id}",
        "/api/graph/{graph_id}/path", "/api/graph/{graph_id}/query/{name}", "/api/queries", "/api/health",
    } <= paths  # fmt: skip
