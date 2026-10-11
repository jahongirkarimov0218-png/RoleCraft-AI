"""Command line: ``promptgraphify analyze | validate | explain | path | query | diff | serve | openapi``.

Exit codes (stable, documented in README):

* 0  success; ``diff``: no differences; ``validate``: no finding at the failing severity
* 1  findings: ``validate``/``analyze --fail-on`` found diagnostics, or ``diff`` found differences
* 2  usage or input error: bad arguments, unreadable / unsafe / oversized input
* 3  not resolved: a name matched nothing or several things, or there is no path
* 4  unsupported or invalid graph file (wrong schema_version, fails the Layer C invariants)
* 5  internal error (a bug; the message names the exception type only)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Sequence
from pathlib import Path

from . import __version__, graphjson
from .analyze import AnalysisError, analyze
from .collect import CollectError, Limits, collect
from .diff import DiffResult, diff_documents
from .exporters import FORMATS, render
from .graphjson import UnsupportedGraph
from .ir import AnalysisConfig, GraphDocument
from .llm import LlmConfigError, get_adapter
from .queries import QUERY_NAMES, QUERY_SPECS, QueryResult, explain_node, run_query
from .validate import GraphInvalid, validate_document

OK, FINDINGS, USAGE, NOT_RESOLVED, BAD_GRAPH, INTERNAL = 0, 1, 2, 3, 4, 5
DEFAULT_OUT = "promptgraphify-out"
DEFAULT_FORMATS = ("json", "html", "report")
MAX_GRAPH_BYTES = 64_000_000
SEVERITY_RANK = {"info": 0, "warning": 1, "error": 2}


class CliError(Exception):
    def __init__(self, message: str, code: int = USAGE):
        super().__init__(message)
        self.code = code


# ---------------------------------------------------------------------------------------------- loading
def _read_graph_file(path: Path) -> GraphDocument:
    try:
        size = path.stat().st_size
    except OSError as exc:
        raise CliError(f"{path}: {exc.strerror or exc}") from exc
    if size > MAX_GRAPH_BYTES:
        raise CliError(f"{path}: larger than {MAX_GRAPH_BYTES} bytes", BAD_GRAPH)
    try:
        return graphjson.loads(path.read_text(encoding="utf-8"))
    except UnicodeDecodeError as exc:
        raise CliError(f"{path}: not valid UTF-8", BAD_GRAPH) from exc
    except UnsupportedGraph as exc:
        raise CliError(f"{path}: {exc}", BAD_GRAPH) from exc
    except GraphInvalid as exc:
        raise CliError(
            f"{path}: the graph breaks {len(exc.violations)} invariant(s), first: {exc.violations[0]}", BAD_GRAPH
        ) from exc


def _looks_like_graph(path: str) -> bool:
    """A ``.json`` file with the three top-level keys of graph.json is meant as a graph, not as a prompt."""
    p = Path(path)
    if p.suffix.lower() != ".json" or not p.is_file():
        return False
    try:
        with p.open("rb") as fh:
            head = fh.read(MAX_GRAPH_BYTES + 1)
        raw = json.loads(head.decode("utf-8"))
    except (OSError, ValueError):
        return False
    return isinstance(raw, dict) and {"graph_id", "nodes", "edges"} <= raw.keys()


def _limits(args: argparse.Namespace) -> Limits:
    return Limits(max_files=args.max_files, max_file_bytes=args.max_file_bytes, max_total_chars=args.max_chars)


def _analyze_paths(paths: list[str], args: argparse.Namespace, skip: list[Path] | None = None) -> GraphDocument:
    try:
        got = collect(paths, _limits(args), skip_dirs=skip)
    except CollectError as exc:
        raise CliError(str(exc)) from exc
    for note in got.notes:
        print(f"note: {note}", file=sys.stderr)
    try:
        return analyze(got.files, AnalysisConfig(layer_b=False), max_input_chars=args.max_chars)
    except AnalysisError as exc:
        raise CliError(str(exc)) from exc


def _document(args: argparse.Namespace) -> GraphDocument:
    """The graph a query-like command works on: ``--graph FILE``, else analyse PATH..., else the default
    ``promptgraphify-out/graph.json`` left by an earlier ``analyze``."""
    paths = getattr(args, "paths", None) or []
    if args.graph and paths:
        raise CliError("give either PATH... or --graph, not both")
    if args.graph:
        return _read_graph_file(Path(args.graph))
    if paths:
        return _analyze_paths(paths, args)
    default = Path(DEFAULT_OUT) / "graph.json"
    if default.is_file():
        return _read_graph_file(default)
    raise CliError(
        f"no input: give PATH..., --graph FILE, or run `promptgraphify analyze` first ({default} is missing)"
    )


def _side(spec: str, args: argparse.Namespace) -> GraphDocument:
    return _read_graph_file(Path(spec)) if _looks_like_graph(spec) else _analyze_paths([spec], args)


# --------------------------------------------------------------------------------------------- printing
def _counts(doc: GraphDocument) -> dict[str, int]:
    sev = {"error": 0, "warning": 0, "info": 0}
    for d in doc.diagnostics:
        sev[d.severity] += 1
    return sev


def _evidence_line(ev) -> str:
    text = " ".join(ev.text.split())
    return f"{ev.source_file}[{ev.span.start},{ev.span.end}): {text[:100]}{'…' if len(text) > 100 else ''}"


def format_query(result: QueryResult) -> str:
    lines = [result.summary]
    if result.status == "ambiguous":
        lines.append("Candidates (pass a longer part of the text or the node id):")
        lines += [f"  - {c.type} {c.label!r}  id={c.id}" for c in result.candidates]
    for i, row in enumerate(result.rows, 1):
        lines.append(f"{i}. {row.title} — {row.detail} [{row.basis}]")
        lines += [f"     evidence: {_evidence_line(ev)}" for ev in row.evidence[:2]]
    if result.paths:
        by_id = {n.id: n.label for n in result.nodes}
        for p in result.paths:
            lines.append("path: " + " → ".join(by_id.get(x, x) for x in p))
    return "\n".join(lines)


def _query_exit(result: QueryResult) -> int:
    return {"ok": OK, "invalid": USAGE}.get(result.status, NOT_RESOLVED)


def _emit(args: argparse.Namespace, payload, text: str) -> None:
    if args.json:
        print(
            json.dumps(
                payload.model_dump(mode="json") if hasattr(payload, "model_dump") else payload,
                indent=2,
                sort_keys=True,
                ensure_ascii=False,
            )
        )
    else:
        print(text)


def format_diff(d: DiffResult) -> str:
    s = d.summary
    if d.identical:
        return f"No differences (graph {d.new_graph_id})."
    lines = [
        f"Differences between {d.old_graph_id} and {d.new_graph_id}:",
        f"  nodes added {s.nodes_added}, removed {s.nodes_removed}, probably modified {s.probably_modified}",
        f"  dependencies added {s.dependencies_added}, removed {s.dependencies_removed}; "
        f"constraints changed {s.constraints_changed}",
        f"  execution sequence changed: {'yes' if s.sequence_changed else 'no'}; "
        f"diagnostics new {s.diagnostics_new}, resolved {s.diagnostics_resolved}",
    ]

    def block(title: str, rows: list[str]) -> None:
        if rows:
            lines.append(f"\n{title}")
            lines.extend(f"  {r}" for r in rows)

    block("Added nodes", [f"+ {n.type} {n.label!r}" for n in d.nodes_added])
    block("Removed nodes", [f"- {n.type} {n.label!r}" for n in d.nodes_removed])
    block(
        "Probably modified (guessed from text similarity, not certain)",
        [
            f"~ {p.old.original_text!r} → {p.new.original_text!r} (similarity {p.similarity})"
            for p in d.probably_modified
        ],
    )
    block(
        "Dependencies", [f"{c.kind}: {c.source_label!r} {c.edge.relation} {c.target_label!r}" for c in d.dependencies]
    )
    block("Constraints", [f"{c.kind}: {c.constraint.label!r} — {c.detail}" for c in d.constraints])
    if d.sequence.changed:
        block(
            "Execution sequence",
            [d.sequence.note, "old: " + " → ".join(d.sequence.old_order), "new: " + " → ".join(d.sequence.new_order)],
        )
    block(
        "New diagnostics",
        [f"{x.diagnostic.severity} {x.diagnostic.rule_id}: {x.diagnostic.description}" for x in d.diagnostics_new],
    )
    block(
        "Resolved diagnostics",
        [f"{x.diagnostic.severity} {x.diagnostic.rule_id}: {x.diagnostic.description}" for x in d.diagnostics_resolved],
    )
    return "\n".join(lines)


# ---------------------------------------------------------------------------------------------- commands
def _selected_formats(raw: list[str] | None) -> list[str]:
    names: list[str] = []
    for chunk in raw or list(DEFAULT_FORMATS):
        names += [x.strip() for x in chunk.split(",") if x.strip()]
    if "all" in names:
        names = list(FORMATS)
    unknown = [n for n in names if n not in FORMATS]
    if unknown:
        raise CliError(f"unknown format(s) {', '.join(unknown)}; choose from {', '.join(FORMATS)}, all")
    return list(dict.fromkeys(names))


def cmd_analyze(args: argparse.Namespace) -> int:
    formats = _selected_formats(args.format)
    out = Path(args.out)
    if out.exists() and not out.is_dir():
        raise CliError(f"--out {out} exists and is not a directory")
    try:
        got = collect(args.paths, _limits(args), skip_dirs=[out])
    except CollectError as exc:
        raise CliError(str(exc)) from exc
    for note in got.notes:
        print(f"note: {note}", file=sys.stderr)
    adapter = None
    if args.llm:
        try:
            adapter = get_adapter()
        except LlmConfigError as exc:
            raise CliError(str(exc)) from exc
        if adapter is None:
            raise CliError("--llm needs a provider: set PROMPTGRAPHIFY_LLM_PROVIDER and _MODEL (see .env.example)")
        print(
            f"note: the LLM layer is on; the prompt text is sent to {adapter.endpoint} (model {adapter.model})",
            file=sys.stderr,
        )
    try:
        doc = analyze(got.files, AnalysisConfig(layer_b=bool(adapter)), max_input_chars=args.max_chars, adapter=adapter)
    except AnalysisError as exc:
        raise CliError(str(exc)) from exc

    views = ["graph", "dag"] if args.view == "both" else [args.view]
    planned: list[tuple[Path, str]] = []
    for name in formats:
        spec = FORMATS[name]
        for view in views if spec.uses_view else ["graph"]:
            file_name = (
                spec.filename.replace("graph", "graph-dag", 1) if view == "dag" and spec.uses_view else spec.filename
            )
            planned.append((out / file_name, render(name, doc, view)[1]))
    inputs = {p.resolve() for p in got.real_paths}
    for target, _ in planned:
        if target.resolve() in inputs:
            raise CliError(f"refusing to overwrite the input file {target}; choose another --out")
    for target, text in planned:
        graphjson.write_atomic(target, text)

    sev = _counts(doc)
    covered = sum(c.covered + c.structural for c in doc.coverage)
    total = sum(c.total for c in doc.coverage)
    uncovered = sum(c.uncovered for c in doc.coverage)
    if args.json:
        print(
            json.dumps(
                {
                    "graph_id": doc.graph_id,
                    "files": [n for n, _ in got.files],
                    "nodes": len(doc.nodes),
                    "edges": len(doc.edges),
                    "diagnostics": sev,
                    "dag_status": doc.dag.status,
                    "warnings": doc.warnings,
                    "coverage": {"accounted": covered, "total": total, "uncovered": uncovered},
                    "written": [str(t) for t, _ in planned],
                },
                indent=2,
                sort_keys=True,
            )
        )
    else:
        print(f"Analyzed {len(got.files)} file(s), graph {doc.graph_id}")
        print(
            f"  nodes {len(doc.nodes)} · edges {len(doc.edges)} · diagnostics {len(doc.diagnostics)} "
            f"(error {sev['error']}, warning {sev['warning']}, info {sev['info']}) · execution DAG: {doc.dag.status}"
        )
        pct = 100.0 if total == 0 else 100.0 * covered / total
        print(f"  coverage: {pct:.1f}% of non-whitespace characters accounted for, {uncovered} left uncovered")
        print("Wrote:")
        for target, _ in planned:
            print(f"  {target}")
        if "html" in formats:
            print(f"Open {out / 'graph.html'} in a browser; it works offline.")
        for note in doc.warnings:
            print(f"note: {note}")
    if args.fail_on != "never" and any(
        SEVERITY_RANK[d.severity] >= SEVERITY_RANK[args.fail_on] for d in doc.diagnostics
    ):
        return FINDINGS
    return OK


def cmd_validate(args: argparse.Namespace) -> int:
    doc = _document(args)
    violations = validate_document(doc) if args.graph else []
    sev = _counts(doc)
    failing = [d for d in doc.diagnostics if SEVERITY_RANK[d.severity] >= SEVERITY_RANK[args.fail_on]]
    if args.json:
        print(
            json.dumps(
                {
                    "graph_id": doc.graph_id,
                    "violations": [str(v) for v in violations],
                    "diagnostics": [d.model_dump(mode="json") for d in doc.diagnostics],
                    "counts": sev,
                },
                indent=2,
                sort_keys=True,
                ensure_ascii=False,
            )
        )
    else:
        print(
            f"Graph {doc.graph_id}: {len(violations)} invariant violation(s); diagnostics: "
            f"error {sev['error']}, warning {sev['warning']}, info {sev['info']}"
        )
        for v in violations:
            print(f"  violation: {v}")
        for d in sorted(doc.diagnostics, key=lambda x: (-SEVERITY_RANK[x.severity], x.id)):
            print(f"  {d.severity} [{d.certainty}] {d.rule_id}: {d.description}")
            if d.evidence:
                print(f"      evidence: {_evidence_line(d.evidence[0])}")
            print(f"      fix: {d.suggested_fix}")
    if violations:
        return BAD_GRAPH
    return FINDINGS if failing else OK


def cmd_explain(args: argparse.Namespace) -> int:
    res = explain_node(_document(args), args.name)
    _emit(args, res, format_query(res))
    return _query_exit(res)


def cmd_path(args: argparse.Namespace) -> int:
    res = run_query(
        _document(args),
        "shortest_path",
        {"source": args.source, "target": args.target, "undirected": str(args.undirected).lower()},
    )
    _emit(args, res, format_query(res).replace("undirected=true", "--undirected"))
    return _query_exit(res)


def cmd_query(args: argparse.Namespace) -> int:
    if args.list_queries:
        for q in QUERY_SPECS:
            params = ", ".join(f"{p.name}{'' if p.required else '?'}" for p in q.params)
            print(f"{q.name:<22} {q.question}" + (f"  [{params}]" if params else ""))
        return OK
    params = {}
    for item in args.param or []:
        key, sep, value = item.partition("=")
        if not sep or not key:
            raise CliError(f"--param expects NAME=VALUE, got {item!r}")
        params[key] = value
    res = run_query(_document(args), args.name, params)
    _emit(args, res, format_query(res))
    return _query_exit(res)


def cmd_diff(args: argparse.Namespace) -> int:
    result = diff_documents(_side(args.old, args), _side(args.new, args))
    _emit(args, result, format_diff(result))
    return OK if result.identical else FINDINGS


def cmd_serve(args: argparse.Namespace) -> int:
    import uvicorn

    if args.host not in ("127.0.0.1", "localhost", "::1"):
        print(
            "warning: the API has no authentication; only bind a non-local address inside a trusted network",
            file=sys.stderr,
        )
    uvicorn.run("promptgraphify.api.app:app", host=args.host, port=args.port, log_level="info")
    return OK


def cmd_openapi(args: argparse.Namespace) -> int:
    from .api.openapi import build

    print(json.dumps(build(), indent=2, sort_keys=True, ensure_ascii=False))
    return OK


# ---------------------------------------------------------------------------------------------- parser
def _inputs(p: argparse.ArgumentParser, *, paths: bool = True) -> None:
    if paths:
        p.add_argument("paths", nargs="*", metavar="PATH", help="prompt files and/or directories to analyse")
    p.add_argument("--graph", metavar="FILE", help="use an existing graph.json instead of analysing PATH")
    _limit_args(p)


def _limit_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--max-files", type=int, default=200, help="most files to read (default 200)")
    p.add_argument("--max-file-bytes", type=int, default=1_000_000, help="largest single file (default 1000000)")
    p.add_argument("--max-chars", type=int, default=500_000, help="most characters over all files (default 500000)")


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        prog="promptgraphify",
        description="Static analysis of LLM prompts: knowledge graph, execution DAG, findings. Community-built; "
        "not affiliated with Graphify Labs.",
        epilog="Exit codes: 0 ok · 1 findings/differences · 2 usage or input error · 3 not resolved · "
        "4 unsupported or invalid graph · 5 internal error",
    )
    ap.add_argument("--version", action="version", version=f"promptgraphify {__version__}")
    sub = ap.add_subparsers(dest="command", required=True, metavar="COMMAND")

    a = sub.add_parser("analyze", help="analyse prompt files and write graph.json, graph.html, GRAPH_REPORT.md")
    a.add_argument("paths", nargs="+", metavar="PATH")
    a.add_argument("--out", default=DEFAULT_OUT, metavar="DIR", help=f"output directory (default ./{DEFAULT_OUT})")
    a.add_argument(
        "--format",
        action="append",
        metavar="NAME[,NAME]",
        help=f"any of {', '.join(FORMATS)}, all (default json,html,report)",
    )
    a.add_argument("--view", choices=["graph", "dag", "both"], default="graph", help="what SVG and Mermaid draw")
    a.add_argument(
        "--fail-on",
        choices=["error", "warning", "info", "never"],
        default="never",
        help="exit 1 if a diagnostic of this severity or worse exists",
    )
    a.add_argument(
        "--llm",
        action="store_true",
        help="also run the optional LLM layer; sends the prompt text to the provider named by PROMPTGRAPHIFY_LLM_*",
    )
    a.add_argument("--json", action="store_true", help="print a machine-readable summary")
    _limit_args(a)
    a.set_defaults(func=cmd_analyze)

    v = sub.add_parser("validate", help="check a graph.json (invariants) or lint prompt files (diagnostics)")
    _inputs(v)
    v.add_argument(
        "--fail-on",
        choices=["error", "warning", "info"],
        default="error",
        help="lowest severity that makes the exit code 1",
    )
    v.add_argument("--json", action="store_true")
    v.set_defaults(func=cmd_validate)

    e = sub.add_parser("explain", help="show one node with every edge and the evidence behind it")
    e.add_argument("name", help="label, id or a unique part of the node's text")
    _inputs(e)
    e.add_argument("--json", action="store_true")
    e.set_defaults(func=cmd_explain)

    pa = sub.add_parser("path", help="shortest path between two nodes")
    pa.add_argument("source")
    pa.add_argument("target")
    _inputs(pa)
    pa.add_argument("--undirected", action="store_true", help="ignore edge direction")
    pa.add_argument("--json", action="store_true")
    pa.set_defaults(func=cmd_path)

    q = sub.add_parser("query", help=f"run a named query ({', '.join(QUERY_NAMES)})")
    q.add_argument("name", nargs="?", default="", help="query name; see --list")
    q.add_argument("--list", dest="list_queries", action="store_true", help="list the queries and exit")
    q.add_argument("--param", action="append", metavar="NAME=VALUE")
    _inputs(q)
    q.add_argument("--json", action="store_true")
    q.set_defaults(func=cmd_query)

    d = sub.add_parser("diff", help="compare two versions of a prompt (files, directories or graph.json)")
    d.add_argument("old")
    d.add_argument("new")
    _limit_args(d)
    d.add_argument("--json", action="store_true")
    d.set_defaults(func=cmd_diff)

    s = sub.add_parser("serve", help="run the HTTP API (and nothing else) on this machine")
    s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--port", type=int, default=8000)
    s.set_defaults(func=cmd_serve)

    o = sub.add_parser("openapi", help="print the OpenAPI document of the HTTP API")
    o.set_defaults(func=cmd_openapi)
    return ap


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    try:
        args = parser.parse_args(argv)
    except SystemExit as exc:  # argparse exits itself (2 on a usage error, 0 for --help / --version)
        return exc.code if isinstance(exc.code, int) else USAGE
    try:
        if args.command == "query" and not args.list_queries and not args.name:
            raise CliError("query needs a name; run `promptgraphify query --list`")
        return args.func(args)
    except CliError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return exc.code
    except KeyboardInterrupt:
        print("interrupted", file=sys.stderr)
        return 130
    except BrokenPipeError:  # the reader closed the pipe (``| head``): not an error; silence the exit-time flush
        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
        return OK
    except Exception as exc:  # noqa: BLE001 - last resort: name the type, never dump internals
        print(f"internal error: {type(exc).__name__}", file=sys.stderr)
        return INTERNAL


if __name__ == "__main__":
    sys.exit(main())
