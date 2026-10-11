"""The command line, run in-process through ``main`` (exit codes, files written) and once as a real process."""

import json
import subprocess
import sys

import pytest

from promptgraphify import __version__, cli, graphjson
from promptgraphify.cli import BAD_GRAPH, FINDINGS, INTERNAL, NOT_RESOLVED, OK, USAGE, main

V1 = (
    "# Task\nYou are a support bot.\n1. Extract the ticket id from {{ticket}}.\n2. Check step 1.\n"
    "3. Summarize step 2.\n\n## Rules\n- Never promise a refund.\n- Keep every answer under 50 words.\n"
)
V2 = V1.replace("Never promise a refund.", "Never promise any refunds.").replace(
    "3. Summarize step 2.", "3. Summarize step 2.\n4. Send step 3."
)


@pytest.fixture()
def proj(tmp_path, monkeypatch):
    (tmp_path / "prompts").mkdir()
    (tmp_path / "prompts" / "v1.md").write_text(V1, encoding="utf-8")
    (tmp_path / "prompts" / "v2.md").write_text(V2, encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    return tmp_path


def run(capsys, *argv):
    code = main([str(a) for a in argv])
    cap = capsys.readouterr()
    return code, cap.out, cap.err


# --------------------------------------------------------------------------------------------- analyze
def test_analyze_writes_the_three_default_files_and_summarises(proj, capsys):
    code, out, err = run(capsys, "analyze", "prompts/v1.md")
    assert code == OK and err == ""
    files = sorted(p.name for p in (proj / "promptgraphify-out").iterdir())
    assert files == ["GRAPH_REPORT.md", "graph.html", "graph.json"]  # nothing else: no temp files left behind
    doc = graphjson.loads((proj / "promptgraphify-out" / "graph.json").read_text(encoding="utf-8"))
    assert doc.graph_id in out and f"nodes {len(doc.nodes)}" in out and "works offline" in out


def test_analyze_is_byte_for_byte_deterministic(proj, capsys):
    run(capsys, "analyze", "prompts", "--out", "a")
    run(capsys, "analyze", "prompts", "--out", "b")
    for name in ("graph.json", "graph.html", "GRAPH_REPORT.md"):
        assert (proj / "a" / name).read_bytes() == (proj / "b" / name).read_bytes()


def test_all_formats_and_both_views(proj, capsys):
    code, _, _ = run(capsys, "analyze", "prompts/v1.md", "--format", "all", "--view", "both", "--out", "o")
    assert code == OK
    assert sorted(p.name for p in (proj / "o").iterdir()) == sorted(
        [
            "GRAPH_REPORT.md",
            "graph-dag.mmd",
            "graph-dag.svg",
            "graph.graphml",
            "graph.html",
            "graph.json",
            "graph.mmd",
            "graph.svg",
        ]
    )


def test_formats_can_be_repeated_or_comma_separated(proj, capsys):
    run(capsys, "analyze", "prompts/v1.md", "--format", "json,svg", "--format", "mermaid", "--out", "o")
    assert sorted(p.name for p in (proj / "o").iterdir()) == ["graph.json", "graph.mmd", "graph.svg"]


def test_unknown_format_is_a_usage_error(proj, capsys):
    code, _, err = run(capsys, "analyze", "prompts/v1.md", "--format", "pdf")
    assert code == USAGE and "unknown format" in err and not (proj / "promptgraphify-out").exists()


def test_fail_on_controls_the_exit_code_but_files_are_still_written(proj, capsys):
    assert run(capsys, "analyze", "prompts/v1.md", "--out", "o")[0] == OK
    code, out, _ = run(capsys, "analyze", "prompts/v1.md", "--out", "o", "--fail-on", "warning")
    assert code == FINDINGS and (proj / "o" / "graph.json").exists()
    assert run(capsys, "analyze", "prompts/v1.md", "--out", "o", "--fail-on", "error")[0] == OK


def test_missing_input_and_unsafe_input_are_usage_errors(proj, capsys):
    assert run(capsys, "analyze", "nope.md")[0] == USAGE
    (proj / "bad.md").write_bytes(b"caf\xe9\n")
    code, _, err = run(capsys, "analyze", "bad.md")
    assert code == USAGE and "not valid UTF-8" in err
    code, _, err = run(capsys, "analyze", "prompts", "--max-files", "1")
    assert code == USAGE and "the limit is 1" in err


def test_output_never_overwrites_an_input_file(proj, capsys):
    prompt_json = proj / "graph.json"  # a prompt that happens to have the output's file name
    prompt_json.write_text('{"system": "You are a bot."}\n', encoding="utf-8")
    before = prompt_json.read_bytes()
    code, _, err = run(capsys, "analyze", "graph.json", "--out", ".")
    assert code == USAGE and "refusing to overwrite" in err and prompt_json.read_bytes() == before


def test_out_that_is_a_file_is_refused(proj, capsys):
    (proj / "afile").write_text("x", encoding="utf-8")
    code, _, err = run(capsys, "analyze", "prompts/v1.md", "--out", "afile")
    assert code == USAGE and "not a directory" in err


def test_output_directory_inside_the_analysed_tree_is_not_read_back(proj, capsys):
    first = run(capsys, "analyze", "prompts", "--out", "prompts/out", "--json")
    second = run(capsys, "analyze", "prompts", "--out", "prompts/out", "--json")
    assert json.loads(first[1])["graph_id"] == json.loads(second[1])["graph_id"]
    assert all("out/" not in f for f in json.loads(second[1])["files"])


def test_json_summary_is_machine_readable(proj, capsys):
    _, out, _ = run(capsys, "analyze", "prompts/v1.md", "--json")
    data = json.loads(out)
    assert data["files"] == ["v1.md"] and data["dag_status"] == "ok" and data["coverage"]["total"] > 0


def test_directory_notes_go_to_stderr(proj, capsys):
    (proj / "prompts" / ".hidden.md").write_text("x\n", encoding="utf-8")
    _, out, err = run(capsys, "analyze", "prompts", "--out", "o")
    assert "skipped hidden file .hidden.md" in err and ".hidden" not in out


# ---------------------------------------------------------------------------- query-like commands
@pytest.fixture()
def analysed(proj, capsys):
    run(capsys, "analyze", "prompts/v1.md")
    return proj


def test_commands_default_to_the_graph_left_by_analyze(analysed, capsys):
    code, out, _ = run(capsys, "explain", "Check step 1.")
    assert code == OK and "TaskNode 'Check step 1.'" in out and "evidence:" in out
    assert run(capsys, "query", "execution_bottleneck")[0] == OK
    assert run(capsys, "validate")[0] == OK


def test_ambiguous_and_missing_names_exit_3_with_candidates(analysed, capsys):
    code, out, _ = run(capsys, "explain", "step")
    assert code == NOT_RESOLVED and "matches 2 nodes" in out and "id=" in out
    assert run(capsys, "explain", "zzz-nothing")[0] == NOT_RESOLVED
    assert run(capsys, "path", "Check step 1.", "zzz-nothing")[0] == NOT_RESOLVED


def test_path_prints_the_route_and_respects_direction(analysed, capsys):
    code, out, _ = run(capsys, "path", "Extract the ticket id from {{ticket}}.", "Summarize step 2.")
    assert code == OK and "path:" in out and out.index("Extract") < out.index("Check step 1.")
    # a constraint points at the task it restricts, never the other way round
    assert run(capsys, "path", "Never promise a refund.", "Check step 1.")[0] == OK
    code, out, _ = run(capsys, "path", "Check step 1.", "Never promise a refund.")
    assert code == NOT_RESOLVED and "No directed path" in out and "--undirected" in out
    assert run(capsys, "path", "Check step 1.", "Never promise a refund.", "--undirected")[0] == OK


def test_query_listing_parameters_and_errors(analysed, capsys):
    code, out, _ = run(capsys, "query", "--list")
    assert code == OK and len([ln for ln in out.splitlines() if ln.strip()]) == 8
    assert run(capsys, "query", "most_dependent", "--param", "top=1")[0] == OK
    assert run(capsys, "query", "most_dependent", "--param", "top")[0] == USAGE  # not NAME=VALUE
    assert run(capsys, "query", "nosuchquery")[0] == USAGE
    assert run(capsys, "query")[0] == USAGE


def test_json_output_of_every_query_like_command_parses(analysed, capsys):
    for argv in (("explain", "Check step 1."), ("path", "Check step 1.", "Summarize step 2."), ("query", "conflicts")):
        code, out, _ = run(capsys, *argv, "--json")
        assert code == OK and json.loads(out)["status"] == "ok"
    code, out, _ = run(capsys, "validate", "--json")
    assert code == OK and {"graph_id", "violations", "diagnostics", "counts"} <= json.loads(out).keys()


def test_input_selection_rules(proj, capsys):
    assert run(capsys, "explain", "x")[0] == USAGE  # no PATH, no --graph, no default graph yet
    run(capsys, "analyze", "prompts/v1.md", "--out", "o")
    code, _, err = run(capsys, "explain", "x", "prompts/v1.md", "--graph", "o/graph.json")
    assert code == USAGE and "not both" in err
    assert run(capsys, "explain", "Check step 1.", "--graph", "o/graph.json")[0] == OK
    assert run(capsys, "explain", "Check step 1.", "prompts/v1.md")[0] == OK  # analyse on the fly


# ------------------------------------------------------------------------------------ graph validation
def test_validate_graph_file_exit_codes(analysed, capsys):
    path = analysed / "promptgraphify-out" / "graph.json"
    assert run(capsys, "validate", "--graph", path)[0] == OK
    raw = json.loads(path.read_text(encoding="utf-8"))

    bad_span = json.loads(json.dumps(raw))
    bad_span["nodes"][0]["original_text"] = "tampered text"
    (analysed / "tampered.json").write_text(json.dumps(bad_span), encoding="utf-8")
    code, out, err = run(capsys, "validate", "--graph", "tampered.json")
    assert code == BAD_GRAPH and "invariant" in err

    old_version = {**raw, "schema_version": "0.9"}
    (analysed / "old.json").write_text(json.dumps(old_version), encoding="utf-8")
    code, _, err = run(capsys, "validate", "--graph", "old.json")
    assert code == BAD_GRAPH and "schema_version" in err and "analyze" in err

    (analysed / "junk.json").write_text("not json", encoding="utf-8")
    assert run(capsys, "validate", "--graph", "junk.json")[0] == BAD_GRAPH
    assert run(capsys, "validate", "--graph", "missing.json")[0] == USAGE


def test_validate_fail_on_severity(analysed, capsys):
    assert run(capsys, "validate")[0] == OK  # warnings only
    assert run(capsys, "validate", "--fail-on", "warning")[0] == FINDINGS
    assert run(capsys, "validate", "--fail-on", "info")[0] == FINDINGS


def test_validate_prompt_files_directly(proj, capsys):
    code, out, _ = run(capsys, "validate", "prompts/v1.md", "--fail-on", "warning")
    assert code == FINDINGS and "variable.undeclared" in out and "fix:" in out


# ---------------------------------------------------------------------------------------------- diff
def test_diff_exit_codes_and_sections(proj, capsys):
    assert run(capsys, "diff", "prompts/v1.md", "prompts/v1.md")[0] == OK
    code, out, _ = run(capsys, "diff", "prompts/v1.md", "prompts/v2.md")
    assert code == FINDINGS and "Added nodes" in out and "Probably modified" in out and "not certain" in out


def test_diff_accepts_graph_files_and_json_output(proj, capsys):
    run(capsys, "analyze", "prompts/v1.md", "--out", "a")
    run(capsys, "analyze", "prompts/v2.md", "--out", "b")
    code, out, _ = run(capsys, "diff", "a/graph.json", "b/graph.json", "--json")
    assert code == FINDINGS and json.loads(out)["summary"]["nodes_added"] == 1
    mixed = run(capsys, "diff", "a/graph.json", "prompts/v2.md", "--json")
    assert json.loads(mixed[1]) == json.loads(out)  # a graph file and the prompt it came from are interchangeable


def test_a_graph_json_with_a_wrong_version_is_not_silently_read_as_a_prompt(proj, capsys):
    run(capsys, "analyze", "prompts/v1.md", "--out", "a")
    raw = json.loads((proj / "a" / "graph.json").read_text(encoding="utf-8"))
    (proj / "old.json").write_text(json.dumps({**raw, "schema_version": "0.1"}), encoding="utf-8")
    code, _, err = run(capsys, "diff", "old.json", "prompts/v1.md")
    assert code == BAD_GRAPH and "schema_version" in err


# ------------------------------------------------------------------------------------------ misc, process
def test_no_command_and_version(capsys):
    assert main([]) == USAGE
    capsys.readouterr()
    assert main(["--version"]) == OK
    assert __version__ in capsys.readouterr().out


def test_openapi_command_prints_the_document(capsys):
    code, out, _ = run(capsys, "openapi")
    assert code == OK and json.loads(out)["info"]["title"] == "PromptGraphify API"


def test_an_unexpected_exception_names_its_type_only(proj, capsys, monkeypatch):
    def boom(*_a, **_k):
        raise RuntimeError("secret internals /home/user/key")

    monkeypatch.setattr(cli, "analyze", boom)
    code, out, err = run(capsys, "analyze", "prompts/v1.md")
    assert code == INTERNAL and "RuntimeError" in err and "secret" not in err + out


def test_real_process_exit_codes(proj):
    def sh(*argv):
        return subprocess.run(
            [sys.executable, "-m", "promptgraphify.cli", *argv], capture_output=True, text=True, timeout=60
        )

    ok = sh("analyze", "prompts/v1.md")
    assert ok.returncode == 0 and "Analyzed 1 file(s)" in ok.stdout
    assert sh("diff", "prompts/v1.md", "prompts/v2.md").returncode == 1
    assert sh("explain", "step").returncode == 3
    assert sh("analyze", "missing.md").returncode == 2
    assert sh("validate", "--graph", "promptgraphify-out/graph.json").returncode == 0


# ------------------------------------------------------------------------------------------ --llm
UNCOVERED = "You are a support bot.\nxyzzy plugh quux.\nSummarize the ticket.\n"


def provider(monkeypatch, answer):
    """A real OpenAI-compatible server on loopback, wired in through the documented environment variables."""
    from .test_llm import Server, completion, reply

    server = Server(lambda h: reply(h, 200, completion(json.dumps(answer))))
    monkeypatch.setenv("PROMPTGRAPHIFY_LLM_PROVIDER", "openai-compatible")
    monkeypatch.setenv("PROMPTGRAPHIFY_LLM_MODEL", "m-1")
    monkeypatch.setenv("PROMPTGRAPHIFY_LLM_BASE_URL", server.url)
    monkeypatch.setenv("PROMPTGRAPHIFY_LLM_API_KEY", "tok_SECRETSECRET1234")
    return server


def test_llm_is_off_by_default_even_when_a_provider_is_configured(proj, capsys, monkeypatch):
    server = provider(monkeypatch, {"nodes": [], "edges": []})
    try:
        (proj / "u.md").write_text(UNCOVERED, encoding="utf-8")
        code, out, err = run(capsys, "analyze", "u.md", "--json")
        assert code == OK and server.requests == [] and json.loads(out)["warnings"] == []
    finally:
        server.close()


def test_llm_flag_runs_the_layer_and_says_where_the_text_goes(proj, capsys, monkeypatch):
    answer = {
        "nodes": [
            {"type": "TaskNode", "file": "u.md", "quote": "xyzzy plugh quux.", "description": "d", "confidence": 0.7}
        ],
        "edges": [],
    }
    server = provider(monkeypatch, answer)
    try:
        (proj / "u.md").write_text(UNCOVERED, encoding="utf-8")
        code, out, err = run(capsys, "analyze", "u.md", "--llm")
        assert code == OK and len(server.requests) == 1
        assert f"sent to 127.0.0.1:{server.httpd.server_address[1]}" in err and "SECRET" not in out + err
        assert "note: layer_b:" in out and "accepted 1 node(s)" in out
        doc = graphjson.loads((proj / "promptgraphify-out" / "graph.json").read_text(encoding="utf-8"))
        assert [n.original_text for n in doc.nodes if n.extraction_method.startswith("llm:")] == ["xyzzy plugh quux."]
    finally:
        server.close()


def test_llm_flag_without_a_provider_is_a_usage_error(proj, capsys, monkeypatch):
    monkeypatch.delenv("PROMPTGRAPHIFY_LLM_PROVIDER", raising=False)
    code, _, err = run(capsys, "analyze", "prompts/v1.md", "--llm")
    assert code == USAGE and "PROMPTGRAPHIFY_LLM_PROVIDER" in err and not (proj / "promptgraphify-out").exists()


def test_llm_flag_with_a_bad_configuration_names_the_variable(proj, capsys, monkeypatch):
    monkeypatch.setenv("PROMPTGRAPHIFY_LLM_PROVIDER", "openai-compatible")
    monkeypatch.delenv("PROMPTGRAPHIFY_LLM_MODEL", raising=False)
    code, _, err = run(capsys, "analyze", "prompts/v1.md", "--llm")
    assert code == USAGE and "PROMPTGRAPHIFY_LLM_MODEL" in err


def test_llm_flag_with_an_unreachable_provider_still_writes_the_deterministic_result(proj, capsys, monkeypatch):
    monkeypatch.setenv("PROMPTGRAPHIFY_LLM_PROVIDER", "openai-compatible")
    monkeypatch.setenv("PROMPTGRAPHIFY_LLM_MODEL", "m-1")
    monkeypatch.setenv("PROMPTGRAPHIFY_LLM_BASE_URL", "http://127.0.0.1:1/v1")
    monkeypatch.setenv("PROMPTGRAPHIFY_LLM_API_KEY", "tok_SECRETSECRET1234")
    code, out, err = run(capsys, "analyze", "prompts/v1.md", "--llm")
    assert code == OK and "cannot reach the provider" in out and "SECRET" not in out + err
    assert (proj / "promptgraphify-out" / "graph.json").exists()
