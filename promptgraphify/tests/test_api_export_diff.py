"""POST /api/diff and GET /api/graph/{id}/export/{format}."""

import io
import json
import xml.etree.ElementTree as ET

import networkx as nx
import pytest
from fastapi.testclient import TestClient

from promptgraphify import graphjson
from promptgraphify.api.app import Settings, create_app
from promptgraphify.api.schemas import ErrorResponse
from promptgraphify.diff import DiffResult
from promptgraphify.storage import SqliteGraphStore

OLD = "1. Extract {{x}}.\n2. Check step 1.\n\nNever promise a refund.\n"
NEW = "1. Extract {{x}}.\n2. Check step 1.\n3. Summarize step 2.\n\nNever promise any refunds.\n"


@pytest.fixture()
def client():
    return TestClient(create_app(Settings(), SqliteGraphStore(":memory:")))


def files(text: str):
    return [{"path": "p.md", "text": text}]


def analyze_id(client, text: str) -> str:
    return client.post("/api/analyze", json={"files": files(text)}).json()["graph_id"]


# --------------------------------------------------------------------------------------------- diff
def test_diff_of_two_file_sets(client):
    r = client.post("/api/diff", json={"old": {"files": files(OLD)}, "new": {"files": files(NEW)}})
    assert r.status_code == 200
    d = DiffResult.model_validate(r.json())
    assert not d.identical and d.summary.nodes_added >= 1 and d.summary.probably_modified == 1
    assert "Summarize step 2." in [n.original_text for n in d.nodes_added]


def test_diff_accepts_stored_graph_ids_and_mixes_both_forms(client):
    a = analyze_id(client, OLD)
    by_ids = client.post("/api/diff", json={"old": {"graph_id": a}, "new": {"files": files(NEW)}}).json()
    both = client.post("/api/diff", json={"old": {"graph_id": a}, "new": {"graph_id": analyze_id(client, NEW)}}).json()
    assert by_ids == both and by_ids["old_graph_id"] == a


def test_diff_of_identical_inputs_is_identical(client):
    r = client.post("/api/diff", json={"old": {"files": files(OLD)}, "new": {"files": files(OLD)}}).json()
    assert r["identical"] is True


def test_diff_unknown_graph_id_is_404(client):
    r = client.post("/api/diff", json={"old": {"graph_id": "0" * 16}, "new": {"files": files(NEW)}})
    assert r.status_code == 404 and ErrorResponse.model_validate(r.json()).error.code == "not_found"


@pytest.mark.parametrize(
    "side",
    [{}, {"graph_id": "0" * 16, "files": files(OLD)}, {"graph_id": "short"}, {"files": []}, {"extra": 1}],
)
def test_diff_rejects_a_malformed_side(client, side):
    r = client.post("/api/diff", json={"old": side, "new": {"files": files(NEW)}})
    assert r.status_code == 422 and ErrorResponse.model_validate(r.json()).error.code == "invalid_request"


def test_diff_enforces_the_input_size_limit():
    small = TestClient(create_app(Settings(max_input_chars=50), SqliteGraphStore(":memory:")))
    r = small.post("/api/diff", json={"old": {"files": files("x" * 200)}, "new": {"files": files(NEW)}})
    assert r.status_code == 413


# ------------------------------------------------------------------------------------------- export
def test_every_format_downloads_with_safe_headers(client):
    gid = analyze_id(client, OLD)
    for fmt in ("json", "html", "report", "mermaid", "graphml", "svg"):
        r = client.get(f"/api/graph/{gid}/export/{fmt}")
        assert r.status_code == 200, fmt
        assert r.headers["content-disposition"].startswith("attachment; filename=")
        assert r.headers["x-content-type-options"] == "nosniff"
        assert "default-src 'none'" in r.headers["content-security-policy"]
        assert r.content


def test_exported_json_is_the_stored_graph(client):
    gid = analyze_id(client, OLD)
    r = client.get(f"/api/graph/{gid}/export/json")
    assert r.headers["content-type"].startswith("application/json")
    assert graphjson.loads(r.text).graph_id == gid
    assert json.loads(r.text) == client.get(f"/api/graph/{gid}").json()


def test_exported_formats_are_readable_by_independent_parsers(client):
    gid = analyze_id(client, OLD)
    ET.fromstring(client.get(f"/api/graph/{gid}/export/svg").content)
    g = nx.read_graphml(io.BytesIO(client.get(f"/api/graph/{gid}/export/graphml").content))
    assert g.graph["graph_id"] == gid
    assert client.get(f"/api/graph/{gid}/export/mermaid").text.startswith("flowchart LR")
    assert client.get(f"/api/graph/{gid}/export/report").text.startswith("# PromptGraphify report")


def test_dag_view_changes_the_picture_and_the_file_name(client):
    gid = analyze_id(client, OLD)
    graph = client.get(f"/api/graph/{gid}/export/svg")
    dag = client.get(f"/api/graph/{gid}/export/svg?view=dag")
    assert graph.content != dag.content and "graph-dag.svg" in dag.headers["content-disposition"]
    assert "graph.svg" in graph.headers["content-disposition"]


def test_export_errors_use_the_envelope(client):
    gid = analyze_id(client, OLD)
    bad_fmt = client.get(f"/api/graph/{gid}/export/pdf")
    assert bad_fmt.status_code == 404 and "known:" in bad_fmt.json()["error"]["message"]
    assert client.get(f"/api/graph/{'0' * 16}/export/json").status_code == 404
    assert client.get(f"/api/graph/{gid}/export/svg?view=bogus").status_code == 422
