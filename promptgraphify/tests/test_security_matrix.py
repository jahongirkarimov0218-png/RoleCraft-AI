"""The robustness list of the spec, end to end: hostile bodies through the API, timeouts and error masking, path
variants, empty input in the CLI, and a scan for invisible / bidirectional characters in the repository itself."""

import json
import re
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from promptgraphify.api import app as app_module
from promptgraphify.api.app import Settings, create_app
from promptgraphify.api.schemas import ErrorResponse
from promptgraphify.cli import main
from promptgraphify.ir import GraphDocument
from promptgraphify.storage import SqliteGraphStore
from promptgraphify.validate import validate_document

ROOT = Path(__file__).parent.parent


@pytest.fixture()
def client():
    return TestClient(create_app(Settings(), SqliteGraphStore(":memory:"), llm=None))


def post(client, path, text):
    return client.post("/api/analyze", json={"files": [{"path": path, "text": text}]})


# ----------------------------------------------------------------------- hostile bodies, end to end
HOSTILE = {
    "deep json arrays": ("p.json", "[" * 100_000 + "]" * 100_000),
    "deep json objects": ("p.json", '{"a":' * 20_000 + "1" + "}" * 20_000),
    "yaml alias bomb": (
        "p.yaml",
        "a: &a [x,x,x,x,x,x,x,x,x]\n"
        + "".join(f"{chr(98 + i)}: &{chr(98 + i)} [" + ",".join(["*" + chr(97 + i)] * 9) + "]\n" for i in range(9)),
    ),
    "yaml python tag": ("p.yaml", "system: !!python/object/apply:os.system ['echo pwned']\ntask: Summarize it.\n"),
    "yaml deep flow": ("p.yaml", "k: " + "[" * 30_000 + "]" * 30_000 + "\n"),
    "xml entity declaration": (
        "p.xml",
        '<!DOCTYPE l [<!ENTITY a "aaaa"><!ENTITY b "&a;&a;&a;&a;">]>\n'
        "<system>&b;</system>\n<task>Summarize it.</task>\n",
    ),
    "xml unclosed flood": ("p.xml", "<a>" * 30_000),
    "unclosed attribute": ("p.xml", '<tool name="x\n<task>Summarize it.</task>'),
    "template flood": ("p.md", "{{" * 40_000),
    "nested templates": ("p.md", "{{ " * 3_000 + "x" + " }}" * 3_000),
    "fence flood": ("p.md", "```\n" * 30_000),
    "combining marks": ("p.txt", "Summarize" + "\u0301" * 50_000 + " it."),
    "controls and bidi": ("p.txt", "You are \u202e a bot\u0000\x01.\nSummarize it.\n"),
    "one huge word": ("p.txt", "a" * 300_000),
    "backslash flood": ("p.json", '{"x": "' + "\\n" * 50_000 + '"}'),
}


@pytest.mark.parametrize("name", sorted(HOSTILE))
def test_hostile_input_gets_a_valid_graph_or_a_clean_error_never_a_crash_or_a_hang(client, name):
    path, text = HOSTILE[name]
    started = time.monotonic()
    r = post(client, path, text)
    assert time.monotonic() - started < 20, f"{name}: {time.monotonic() - started:.1f}s"
    if r.status_code == 200:
        assert validate_document(GraphDocument.model_validate(r.json()["graph"])) == []
    else:
        assert r.status_code in (413, 422) and ErrorResponse.model_validate(r.json())


# ----------------------------------------------------------------------------- path traversal and names
@pytest.mark.parametrize(
    "path",
    [
        "../secret.md",
        "a/../../b.md",
        "/etc/passwd",
        "C:\\Windows\\x.md",
        "C:/x.md",
        "a\\b.md",
        "a\x00b.md",
        "a\nb.md",
        "",
        "x" * 300,
        "..",
    ],
)
def test_unsafe_file_names_are_rejected_before_any_analysis(client, path):
    r = post(client, path, "Summarize it.")
    assert r.status_code == 422 and r.json()["error"]["code"] == "invalid_request"


def test_a_leading_dot_slash_is_normalised_not_trusted(client):
    r = post(client, "./sub/./p.md", "Summarize it.")
    assert r.status_code == 200 and r.json()["graph"]["sources"][0]["path"] == "sub/p.md"


def test_file_count_duplicate_paths_and_size_limits(client):
    many = {"files": [{"path": f"f{i}.md", "text": "Be brief."} for i in range(201)]}
    assert client.post("/api/analyze", json=many).status_code == 422
    dup = {"files": [{"path": "a.md", "text": "x"}, {"path": "./a.md", "text": "y"}]}
    r = client.post("/api/analyze", json=dup)
    assert r.status_code == 422 and r.json()["error"]["code"] in ("duplicate_path", "invalid_request")
    small = TestClient(
        create_app(Settings(max_input_chars=100, max_request_bytes=10_000), SqliteGraphStore(":memory:"), llm=None)
    )
    assert post(small, "p.md", "x" * 500).status_code == 413
    assert (
        small.post("/api/analyze", content=b"x" * 50_000, headers={"content-type": "application/json"}).status_code
        == 413
    )


# ----------------------------------------------------------------------- timeouts and error masking
def slow_app(monkeypatch):
    def slow(*_a, **_k):
        time.sleep(1.5)
        raise AssertionError("the response should already have been sent")

    monkeypatch.setattr(app_module, "analyze", slow)
    return create_app(Settings(analyze_timeout_s=0.2), SqliteGraphStore(":memory:"), llm=None)


def test_a_slow_analysis_is_answered_with_a_clean_504(monkeypatch):
    r = post(TestClient(slow_app(monkeypatch)), "p.md", "Summarize it.")
    assert r.status_code == 504 and r.json()["error"]["code"] == "timeout"


def test_the_504_is_sent_when_the_deadline_passes_not_when_the_work_finishes(monkeypatch):
    """Against a real server: the analysis thread cannot be killed, but the client must not wait for it."""
    import threading
    import urllib.error
    import urllib.request

    import uvicorn

    server = uvicorn.Server(uvicorn.Config(slow_app(monkeypatch), host="127.0.0.1", port=0, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.monotonic() + 10
    while not server.started and time.monotonic() < deadline:
        time.sleep(0.02)
    port = server.servers[0].sockets[0].getsockname()[1]
    request = urllib.request.Request(  # noqa: S310 - loopback test server
        f"http://127.0.0.1:{port}/api/analyze",
        json.dumps({"files": [{"path": "p.md", "text": "x"}]}).encode(),
        {"content-type": "application/json"},
    )
    started = time.monotonic()
    try:
        urllib.request.urlopen(request, timeout=10)  # noqa: S310
        status = 200
    except urllib.error.HTTPError as exc:
        status = exc.code
    elapsed = time.monotonic() - started
    server.should_exit = True
    thread.join(5)
    assert status == 504 and elapsed < 1.0, f"{status} after {elapsed:.2f}s (deadline 0.2s, work 1.5s)"


def test_an_unexpected_error_returns_a_generic_message_and_logs_only_the_type(monkeypatch, capsys):
    def boom(*_a, **_k):
        raise RuntimeError("internal detail: key sk-abcdefghijklmnop at /home/user/secret")

    monkeypatch.setattr(app_module, "analyze", boom)
    c = TestClient(create_app(Settings(), SqliteGraphStore(":memory:"), llm=None), raise_server_exceptions=False)
    r = post(c, "p.md", "Summarize it.")
    out = capsys.readouterr().out
    assert r.status_code == 500 and r.json()["error"] == {
        "code": "internal_error",
        "message": "unexpected server error",
    }
    assert "RuntimeError" in out and "sk-abcdefghijklmnop" not in out + r.text and "/home/user" not in out + r.text


def test_validation_errors_do_not_echo_the_submitted_text(client):
    secret = "TOP-SECRET-PROMPT-TEXT"
    r = client.post("/api/analyze", json={"files": [{"path": "p.md", "text": secret, "extra": 1}]})
    assert r.status_code == 422 and secret not in r.text


# ------------------------------------------------------------------------------------------- CLI inputs
@pytest.mark.parametrize("content", ["", "   \n\t\n  \n", "\ufeff", "\r\n\r\n"])
def test_an_empty_or_blank_file_analyses_to_an_empty_honest_graph(tmp_path, monkeypatch, capsys, content):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "blank.md").write_bytes(content.encode("utf-8"))
    assert main(["analyze", "blank.md", "--json"]) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["nodes"] == 0 and data["edges"] == 0
    graph = json.loads((tmp_path / "promptgraphify-out" / "graph.json").read_text(encoding="utf-8"))
    assert [d["rule_id"] for d in graph["diagnostics"]] == ["input.empty"]


# ----------------------------------------------------------------- invisible characters in our own source
INVISIBLE = re.compile(
    "[\u202a-\u202e\u2066-\u2069\u200b-\u200f\u2060\ufeff\u00ad]"
)  # bidi controls, zero-width, BOM, soft hyphen
SCANNED = [
    ("src", "*.py"),
    ("src", "*.json"),
    ("tests", "*.py"),
    ("web/src", "*.ts*"),
    ("web/e2e", "*.ts"),
    ("docs", "*.md"),
    ("eval", "*.md"),
]


def test_the_repository_sources_contain_no_invisible_or_bidirectional_characters():
    """Trojan Source: a bidi control or zero-width character can make code read differently from how it runs.
    Test data that needs one builds it with chr() or an escape; fixtures and datasets are exempt (their content
    is the point)."""
    offenders = []
    for folder, pattern in SCANNED:
        for path in sorted((ROOT / folder).rglob(pattern)):
            if "node_modules" in path.parts or ".next" in path.parts or "fixtures" in path.parts:
                continue
            text = path.read_text(encoding="utf-8")
            for m in INVISIBLE.finditer(text):
                line = text.count("\n", 0, m.start()) + 1
                offenders.append(f"{path.relative_to(ROOT)}:{line}: U+{ord(m.group()):04X}")
    assert offenders == [], "\n".join(offenders)
