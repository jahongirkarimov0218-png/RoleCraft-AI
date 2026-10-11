"""The optional LLM layer through the HTTP API (fake provider, no network)."""

import pytest
from fastapi.testclient import TestClient

from promptgraphify.api.app import Settings, create_app
from promptgraphify.api.schemas import ErrorResponse, Health
from promptgraphify.ir import GraphDocument
from promptgraphify.llm import LlmConfigError
from promptgraphify.storage import SqliteGraphStore

from .fake_llm import FakeAdapter

TEXT = "You are a support bot.\nxyzzy plugh quux.\nSummarize the ticket.\n"
ANSWER = {
    "nodes": [
        {"type": "TaskNode", "file": "p.md", "quote": "xyzzy plugh quux.", "description": "d", "confidence": 0.7}
    ],
    "edges": [],
}


def client(llm, **settings):
    return TestClient(create_app(Settings(**settings), SqliteGraphStore(":memory:"), llm=llm))


def body(layer_b=None):
    b = {"files": [{"path": "p.md", "text": TEXT}]}
    if layer_b is not None:
        b["layer_b"] = layer_b
    return b


def test_health_says_what_is_configured_and_where_the_prompt_would_go():
    h = Health.model_validate(client(FakeAdapter(ANSWER)).get("/api/health").json())
    assert (h.llm_enabled, h.llm_provider, h.llm_model, h.llm_endpoint) == (
        True,
        "fake",
        "fake-model-1",
        "fake.invalid",
    )
    off = Health.model_validate(client(None).get("/api/health").json())
    assert (off.llm_enabled, off.llm_provider, off.llm_model, off.llm_endpoint) == (False, None, None, None)


def test_a_normal_request_never_touches_the_provider():
    fake = FakeAdapter(RuntimeError("must not be called"))
    c = client(fake)
    for layer_b in (None, False):
        r = c.post("/api/analyze", json=body(layer_b))
        assert r.status_code == 200 and r.json()["graph"]["config"]["layer_b"] is False
    c.post("/api/validate", json={"files": body()["files"]})
    c.post("/api/diff", json={"old": {"files": body()["files"]}, "new": {"files": body()["files"]}})
    assert fake.calls == []


def test_layer_b_adds_marked_inferred_nodes_and_notes_what_it_did():
    fake = FakeAdapter(ANSWER)
    r = client(fake).post("/api/analyze", json=body(True))
    assert r.status_code == 200 and len(fake.calls) == 1
    doc = GraphDocument.model_validate(r.json()["graph"])
    llm = [n for n in doc.nodes if n.extraction_method == "llm:fake"]
    assert [n.original_text for n in llm] == ["xyzzy plugh quux."] and llm[0].confidence < 1
    assert doc.config.layer_b is True and any("accepted 1 node(s)" in w for w in doc.warnings)


def test_layer_b_without_a_provider_is_503_llm_unavailable():
    r = client(None).post("/api/analyze", json=body(True))
    assert r.status_code == 503 and ErrorResponse.model_validate(r.json()).error.code == "llm_unavailable"


def test_a_failing_provider_still_returns_the_deterministic_result_with_a_warning():
    r = client(FakeAdapter(RuntimeError("boom with sk-abcdefghijkl"))).post("/api/analyze", json=body(True))
    assert r.status_code == 200
    doc = GraphDocument.model_validate(r.json()["graph"])
    assert [n.original_text for n in doc.nodes] == ["You are a support bot.", "Summarize the ticket."]
    assert any("layer_b: unavailable" in w for w in doc.warnings) and "sk-abcdefghijkl" not in r.text


def test_the_stored_graph_keeps_the_llm_nodes_and_a_plain_analysis_is_a_different_graph():
    c = client(FakeAdapter(ANSWER))
    with_llm = c.post("/api/analyze", json=body(True)).json()
    plain = c.post("/api/analyze", json=body(False)).json()
    assert with_llm["graph_id"] != plain["graph_id"]
    stored = c.get(f"/api/graph/{with_llm['graph_id']}").json()
    assert any(n["extraction_method"] == "llm:fake" for n in stored["nodes"])


def test_bad_llm_environment_fails_at_start_up_and_names_the_variable(monkeypatch):
    monkeypatch.setenv("PROMPTGRAPHIFY_LLM_PROVIDER", "openai-compatible")
    monkeypatch.delenv("PROMPTGRAPHIFY_LLM_MODEL", raising=False)
    with pytest.raises(LlmConfigError, match="PROMPTGRAPHIFY_LLM_MODEL"):
        create_app(Settings(), SqliteGraphStore(":memory:"))


def test_the_environment_configures_the_default_adapter(monkeypatch):
    monkeypatch.setenv("PROMPTGRAPHIFY_LLM_PROVIDER", "openai-compatible")
    monkeypatch.setenv("PROMPTGRAPHIFY_LLM_MODEL", "m-1")
    monkeypatch.setenv("PROMPTGRAPHIFY_LLM_BASE_URL", "http://127.0.0.1:9/v1")
    monkeypatch.setenv("PROMPTGRAPHIFY_LLM_API_KEY", "tok_SECRETSECRET1234")
    app = create_app(Settings(), SqliteGraphStore(":memory:"))
    r = TestClient(app).get("/api/health")
    assert r.json()["llm_endpoint"] == "127.0.0.1:9" and "SECRET" not in r.text
    # the port is closed: the request degrades to the deterministic result instead of failing
    out = TestClient(app).post("/api/analyze", json=body(True))
    assert out.status_code == 200 and any("cannot reach the provider" in w for w in out.json()["graph"]["warnings"])
    assert "SECRET" not in out.text
