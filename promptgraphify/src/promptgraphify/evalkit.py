# ruff: noqa: E501
"""Precision / recall of the extraction against a hand-labelled dataset (``eval/dataset``).

Run: ``python -m promptgraphify.evalkit --split dev`` (deterministic layer) and add ``--llm`` to also measure the
optional LLM layer; without a configured provider the LLM part is reported as "not run", never estimated.

What the numbers mean (also written into every report):
* The labels were written by the same assistant that wrote the analyzer, before looking at its output, and have
  ``review_status: unreviewed``: they are an *unreviewed* reference, not ground truth. Agreement with them shows
  consistency with that annotator's reading, not accuracy against independent humans.
* ``dev`` was used to find and fix defects; ``holdout`` was run once, after the dev work was finished.
* Node match is strict: the same type and exactly the same span. Relaxed match ignores the type.
* An edge is scored only for the relations listed in the record's ``relations_complete`` (the relations whose
  edges the annotator labelled exhaustively for that record); unlabelled predicted edges of those relations
  count as false positives.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC
from pathlib import Path
from typing import Any

from . import __version__
from .analyze import analyze
from .ir import AnalysisConfig, GraphDocument
from .layer_b import PROMPT_VERSION
from .llm import LlmAdapter, LlmConfigError, get_adapter
from .ontology import NODE_TYPES, RELATION_TABLE, RELATIONS

FORMATS = {"txt", "md", "xml", "yaml", "json"}
LANGS = ("en", "ru", "uz")
SYMMETRIC = frozenset(name for name, spec in RELATION_TABLE.items() if spec.symmetric)
CAVEATS = (
    "Labels were written by the assistant that built the analyzer, from the text alone and before any parser output "
    "was looked at; every record is `review_status: unreviewed` and no human has reviewed it. Results show agreement "
    "with that reading, not accuracy against independent annotators. `dev` was used to find defects; `holdout` was "
    "run once after the dev work was finished. Datasets this small give wide uncertainty: differences of a few "
    "points are not evidence."
)


class DatasetError(ValueError):
    """The dataset file is malformed (reported with the record id)."""


Span = tuple[int, int]


@dataclass(frozen=True)
class Record:
    id: str
    lang: str
    split: str
    fmt: str
    text: str
    nodes: list[tuple[str, Span, str]]  # (type, span, quote)
    edges: list[tuple[str, Span, Span]]  # (relation, source span, target span)
    relations_complete: frozenset[str]

    @property
    def path(self) -> str:
        return f"p.{self.fmt}"


def resolve_quote(text: str, quote: str, occurrence: int | None) -> Span:
    """Code-point span of ``quote``: the only occurrence, or the ``occurrence``-th (1-based) if stated."""
    hits, i = [], text.find(quote)
    while quote and i != -1:
        hits.append((i, i + len(quote)))
        i = text.find(quote, i + 1)
    if not hits:
        raise DatasetError(f"quote not found: {quote!r}")
    if occurrence is None:
        if len(hits) > 1:
            raise DatasetError(f"quote occurs {len(hits)} times, state which one: {quote!r}")
        return hits[0]
    if not 1 <= occurrence <= len(hits):
        raise DatasetError(f"occurrence {occurrence} of {quote!r} does not exist")
    return hits[occurrence - 1]


def parse_record(raw: dict[str, Any]) -> Record:
    rid = raw.get("id", "?")
    try:
        if raw.get("review_status") != "unreviewed":
            raise DatasetError("review_status must be 'unreviewed' (labels are not human-reviewed)")
        if raw["lang"] not in LANGS or raw["format"] not in FORMATS:
            raise DatasetError("unknown lang or format")
        text = raw["text"]
        nodes: list[tuple[str, Span, str]] = []
        by_quote: dict[str, Span] = {}
        for n in raw["nodes"]:
            if n["type"] not in NODE_TYPES:
                raise DatasetError(f"unknown node type {n['type']!r}")
            span = resolve_quote(text, n["quote"], n.get("occurrence"))
            if n["quote"] in by_quote:
                raise DatasetError(f"two labelled nodes share the quote {n['quote']!r}")
            by_quote[n["quote"]] = span
            nodes.append((n["type"], span, n["quote"]))
        if len({s for _, s, _ in nodes}) != len(nodes):
            raise DatasetError("two labelled nodes share a span")
        edges: list[tuple[str, Span, Span]] = []
        for e in raw["edges"]:
            if e["relation"] not in RELATIONS:
                raise DatasetError(f"unknown relation {e['relation']!r}")
            if e["source"] not in by_quote or e["target"] not in by_quote:
                raise DatasetError(f"edge endpoint is not a labelled node: {e}")
            edges.append((e["relation"], by_quote[e["source"]], by_quote[e["target"]]))
        complete = frozenset(raw["relations_complete"])
        if not complete <= set(RELATIONS):
            raise DatasetError("relations_complete has an unknown relation")
        if any(r not in complete for r, _, _ in edges):
            raise DatasetError("an edge has a relation that is not listed in relations_complete")
        if not nodes:
            raise DatasetError("a record needs at least one node")
        return Record(rid, raw["lang"], raw["split"], raw["format"], text, nodes, edges, complete)
    except KeyError as exc:
        raise DatasetError(f"{rid}: missing field {exc}") from exc
    except DatasetError as exc:
        raise DatasetError(f"{rid}: {exc}") from exc


def load_dataset(path: Path) -> list[Record]:
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            records.append(parse_record(json.loads(line)))
    ids = [r.id for r in records]
    if len(set(ids)) != len(ids):
        raise DatasetError(f"{path.name}: duplicate record ids")
    return records


# ------------------------------------------------------------------------------------------- scoring
@dataclass
class Counts:
    tp: int = 0
    fp: int = 0
    fn: int = 0

    def add(self, other: Counts) -> None:
        self.tp, self.fp, self.fn = self.tp + other.tp, self.fp + other.fp, self.fn + other.fn

    def metrics(self) -> dict[str, Any]:
        p = self.tp / (self.tp + self.fp) if self.tp + self.fp else None
        r = self.tp / (self.tp + self.fn) if self.tp + self.fn else None
        f = 2 * p * r / (p + r) if p and r else (0.0 if p is not None and r is not None else None)
        rnd = lambda v: None if v is None else round(v, 4)  # noqa: E731
        return {"tp": self.tp, "fp": self.fp, "fn": self.fn, "precision": rnd(p), "recall": rnd(r), "f1": rnd(f)}


@dataclass
class Scores:
    nodes_strict: Counts = field(default_factory=Counts)
    nodes_relaxed: Counts = field(default_factory=Counts)
    by_type: dict[str, Counts] = field(default_factory=lambda: defaultdict(Counts))
    by_relation: dict[str, Counts] = field(default_factory=lambda: defaultdict(Counts))
    misses: list[str] = field(default_factory=list)


def _edge_key(relation: str, a: Span, b: Span) -> tuple[str, Span, Span]:
    return (relation, *sorted((a, b))) if relation in SYMMETRIC else (relation, a, b)  # type: ignore[return-value]


def score_record(rec: Record, doc: GraphDocument, scores: Scores) -> None:
    exp_nodes = {(t, s) for t, s, _ in rec.nodes}
    pred_nodes = {(n.type, (n.source_span.start, n.source_span.end)) for n in doc.nodes if n.source_file == rec.path}
    scores.nodes_strict.add(
        Counts(len(exp_nodes & pred_nodes), len(pred_nodes - exp_nodes), len(exp_nodes - pred_nodes))
    )
    exp_spans, pred_spans = {s for _, s in exp_nodes}, {s for _, s in pred_nodes}
    scores.nodes_relaxed.add(
        Counts(len(exp_spans & pred_spans), len(pred_spans - exp_spans), len(exp_spans - pred_spans))
    )
    types = {t for t, _ in exp_nodes | pred_nodes}
    for t in types:
        e = {s for ty, s in exp_nodes if ty == t}
        p = {s for ty, s in pred_nodes if ty == t}
        scores.by_type[t].add(Counts(len(e & p), len(p - e), len(e - p)))
    text = rec.text
    for t, s in sorted(exp_nodes - pred_nodes, key=lambda x: x[1]):
        scores.misses.append(f"{rec.id}: missed {t} {text[s[0] : s[1]]!r}")
    for t, s in sorted(pred_nodes - exp_nodes, key=lambda x: x[1]):
        scores.misses.append(f"{rec.id}: extra {t} {text[s[0] : s[1]]!r}")

    by_id = {n.id: n for n in doc.nodes}
    span_of = {i: (n.source_span.start, n.source_span.end) for i, n in by_id.items() if n.source_file == rec.path}
    exp_edges = {_edge_key(r, a, b) for r, a, b in rec.edges}
    pred_edges = {
        _edge_key(e.relation, span_of[e.source], span_of[e.target])
        for e in doc.edges
        if e.relation in rec.relations_complete and e.source in span_of and e.target in span_of
    }
    for relation in rec.relations_complete:
        e = {k for k in exp_edges if k[0] == relation}
        p = {k for k in pred_edges if k[0] == relation}
        scores.by_relation[relation].add(Counts(len(e & p), len(p - e), len(e - p)))
    for k in sorted(exp_edges - pred_edges, key=repr):
        scores.misses.append(f"{rec.id}: missed edge {k[0]} {text[k[1][0] : k[1][1]]!r} -> {text[k[2][0] : k[2][1]]!r}")
    for k in sorted(pred_edges - exp_edges, key=repr):
        scores.misses.append(f"{rec.id}: extra edge {k[0]} {text[k[1][0] : k[1][1]]!r} -> {text[k[2][0] : k[2][1]]!r}")


def _summarise(records: list[Record], docs: dict[str, GraphDocument]) -> dict[str, Any]:
    overall, by_lang = Scores(), {lang: Scores() for lang in LANGS}
    for rec in records:
        score_record(rec, docs[rec.id], overall)
        score_record(rec, docs[rec.id], by_lang[rec.lang])
    edge_total = Counts()
    for c in overall.by_relation.values():
        edge_total.add(c)

    def block(s: Scores) -> dict[str, Any]:
        et = Counts()
        for c in s.by_relation.values():
            et.add(c)
        return {
            "nodes_strict": s.nodes_strict.metrics(),
            "nodes_relaxed_type_ignored": s.nodes_relaxed.metrics(),
            "edges_all_scored_relations": et.metrics(),
        }

    return {
        "records": len(records),
        "overall": block(overall),
        "by_language": {lang: block(s) for lang, s in by_lang.items() if any(r.lang == lang for r in records)},
        "by_node_type": {t: overall.by_type[t].metrics() for t in NODE_TYPES if t in overall.by_type},
        "by_relation": {r: overall.by_relation[r].metrics() for r in RELATIONS if r in overall.by_relation},
        "misses": overall.misses,
    }


def evaluate(
    records: list[Record], adapter: LlmAdapter | None = None, *, layer_b: bool = False
) -> tuple[dict[str, Any], dict[str, GraphDocument]]:
    docs = {
        r.id: analyze({r.path: r.text}, AnalysisConfig(layer_b=layer_b), adapter=adapter if layer_b else None)
        for r in records
    }
    return _summarise(records, docs), docs


# ------------------------------------------------------------------------------------------- reporting
def _pct(v: float | None) -> str:
    return "n/a" if v is None else f"{v * 100:.1f}%"


def render_markdown(result: dict[str, Any]) -> str:
    lines = [f"# Extraction evaluation: {result['split']}", ""]
    lines.append(
        f"Analyzer {result['analyzer_version']} · dataset sha256 `{result['dataset_sha256'][:16]}` · {result['records']} records"
    )
    lines += ["", f"> {CAVEATS}", ""]

    def table(rows: dict[str, dict[str, Any]], first: str) -> list[str]:
        out = [f"| {first} | precision | recall | F1 | TP | FP | FN |", "|---|---|---|---|---|---|---|"]
        for name, m in rows.items():
            out.append(
                f"| {name} | {_pct(m['precision'])} | {_pct(m['recall'])} | {_pct(m['f1'])} | {m['tp']} | {m['fp']} | {m['fn']} |"
            )
        return out

    det = result["deterministic"]
    lines += ["## Deterministic layer", ""]
    lines += table(
        {
            "nodes (strict: type + span)": det["overall"]["nodes_strict"],
            "nodes (span only)": det["overall"]["nodes_relaxed_type_ignored"],
            "edges (scored relations)": det["overall"]["edges_all_scored_relations"],
        },
        "metric",
    )
    lines += ["", "### By language (nodes, strict)", ""] + table(
        {k: v["nodes_strict"] for k, v in det["by_language"].items()}, "language"
    )
    lines += ["", "### By node type (strict)", ""] + table(det["by_node_type"], "type")
    lines += ["", "### By relation", ""] + table(det["by_relation"], "relation")
    llm = result["llm"]
    lines += ["", "## LLM layer", ""]
    if llm["status"] != "run":
        lines.append(f"**Not run.** {llm['reason']}")
    else:
        lines.append(
            f"Model `{llm['model']}` at `{llm['endpoint']}`, prompt version {llm['prompt_version']}, run at {llm['run_at']}."
        )
        lines += [""] + table(
            {"nodes (strict)": llm["overall"]["nodes_strict"], "edges": llm["overall"]["edges_all_scored_relations"]},
            "metric",
        )
    lines += ["", "## Misses and extras (deterministic)", ""]
    lines += [f"- {m}" for m in det["misses"]] or ["- none"]
    return "\n".join(lines) + "\n"


def run_split(
    split: str, dataset_dir: Path, *, use_llm: bool, adapter: LlmAdapter | None, now: str | None = None
) -> dict[str, Any]:
    path = dataset_dir / f"{split}.jsonl"
    records = load_dataset(path)
    deterministic, _ = evaluate(records)
    result: dict[str, Any] = {
        "split": split,
        "analyzer_version": __version__,
        "dataset_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "records": len(records),
        "caveats": CAVEATS,
        "deterministic": deterministic,
    }
    if not use_llm:
        result["llm"] = {"status": "not run", "reason": "Not requested (pass --llm)."}
    elif adapter is None:
        result["llm"] = {
            "status": "not run",
            "reason": "No provider is configured (PROMPTGRAPHIFY_LLM_PROVIDER / _MODEL).",
        }
    else:
        summary, docs = evaluate(records, adapter, layer_b=True)
        result["llm"] = {
            "status": "run", "model": adapter.model, "adapter": adapter.name, "endpoint": adapter.endpoint,
            "prompt_version": PROMPT_VERSION, "run_at": now or "unknown", "overall": summary["overall"],
            "by_language": summary["by_language"], "warnings": sorted({w for d in docs.values() for w in d.warnings})[:20],
        }  # fmt: skip
    return result


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m promptgraphify.evalkit", description=__doc__.split("\n")[0])
    ap.add_argument("--split", choices=["dev", "holdout"], default="dev")
    ap.add_argument("--dataset-dir", default="eval/dataset")
    ap.add_argument("--out", default="eval/results", help="directory for <split>.json and <split>.md")
    ap.add_argument(
        "--llm", action="store_true", help="also evaluate the optional LLM layer (needs a provider; sends text)"
    )
    ap.add_argument("--details", action="store_true", help="print the misses and extras")
    args = ap.parse_args(argv)
    adapter = None
    if args.llm:
        try:
            adapter = get_adapter()
        except LlmConfigError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
        if adapter:
            print(
                f"note: the LLM layer is on; dataset text is sent to {adapter.endpoint} (model {adapter.model})",
                file=sys.stderr,
            )
    from datetime import datetime

    result = run_split(
        args.split,
        Path(args.dataset_dir),
        use_llm=args.llm,
        adapter=adapter,
        now=datetime.now(UTC).isoformat(timespec="seconds"),
    )
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    suffix = args.split
    (out / f"{suffix}.json").write_text(
        json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    (out / f"{suffix}.md").write_text(render_markdown(result), encoding="utf-8")
    det = result["deterministic"]["overall"]
    n, e = det["nodes_strict"], det["edges_all_scored_relations"]
    print(
        f"{args.split}: {result['records']} records · nodes P {_pct(n['precision'])} R {_pct(n['recall'])} F1 {_pct(n['f1'])}"
        f" · edges P {_pct(e['precision'])} R {_pct(e['recall'])} F1 {_pct(e['f1'])} · LLM: {result['llm']['status']}"
    )
    if args.details:
        print("\n".join(result["deterministic"]["misses"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
