"""Loads fixtures and turns their hand-written quotes into spans.

The loader never looks at any parser output. ``expected.json`` stores quotes; this module finds them in
the input text. A quote that is missing, or that occurs more than once without ``occurrence``, makes
the fixture invalid, so an expectation can never silently point at the wrong place.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from promptgraphify.spans import Span

FIXTURE_ROOT = Path(__file__).parent / "fixtures"


class QuoteError(AssertionError):
    pass


@dataclass
class Fixture:
    name: str
    path: Path
    files: dict[str, str]  # decoded exactly: no BOM stripping, no newline translation
    raw: dict[str, bytes]
    expected: dict

    @property
    def single_file(self) -> str | None:
        return next(iter(self.files)) if len(self.files) == 1 else None


@dataclass(frozen=True)
class Located:
    file: str
    span: Span
    text: str


@dataclass
class ExpNode:
    key: str
    type: str
    loc: Located
    spec: dict


@dataclass
class ExpEdge:
    relation: str
    source: str
    target: str
    status: str
    evidence: list[Located]
    spec: dict


@dataclass
class Resolved:
    nodes: list[ExpNode] = field(default_factory=list)
    edges: list[ExpEdge] = field(default_factory=list)
    uncovered: list[Located] = field(default_factory=list)


def load_fixtures() -> list[Fixture]:
    out = []
    for d in sorted(p for p in FIXTURE_ROOT.iterdir() if p.is_dir()):
        raw = {
            str(f.relative_to(d)).replace("\\", "/"): f.read_bytes()
            for f in sorted(d.rglob("*"))
            if f.is_file() and f.name != "expected.json"
        }
        files = {k: v.decode("utf-8") for k, v in raw.items()}
        expected = json.loads((d / "expected.json").read_text(encoding="utf-8"))
        out.append(Fixture(d.name, d, files, raw, expected))
    return out


def locate(fx: Fixture, quote: str, occurrence: int | None = None, file: str | None = None) -> Located:
    if file is None:
        if fx.single_file is None:
            raise QuoteError(f"{fx.name}: quote {quote[:40]!r} needs an explicit file (fixture has several)")
        file = fx.single_file
    text = fx.files[file]
    starts, idx = [], text.find(quote)
    while idx != -1:
        starts.append(idx)
        idx = text.find(quote, idx + 1)
    if not quote:
        raise QuoteError(f"{fx.name}: empty quote")
    if not starts:
        raise QuoteError(f"{fx.name}: quote not found in {file}: {quote[:60]!r}")
    if occurrence is None and len(starts) > 1:
        raise QuoteError(f"{fx.name}: quote occurs {len(starts)} times, give 'occurrence': {quote[:60]!r}")
    pick = starts[(occurrence or 1) - 1]
    return Located(file, Span(start=pick, end=pick + len(quote)), quote)


def _evidence_items(fx: Fixture, items: list, nodes: dict[str, ExpNode], source: str, target: str) -> list[Located]:
    out = []
    for item in items:
        spec = {"quote": item} if isinstance(item, str) else dict(item)
        if spec["quote"] == "$source":
            out.append(nodes[source].loc)
        elif spec["quote"] == "$target":
            out.append(nodes[target].loc)
        else:
            out.append(locate(fx, spec["quote"], spec.get("occurrence"), spec.get("file")))
    return out


def resolve(fx: Fixture) -> Resolved:
    exp = fx.expected
    res = Resolved()
    by_key: dict[str, ExpNode] = {}
    for spec in exp.get("nodes", []):
        node = ExpNode(
            spec["key"],
            spec["type"],
            locate(fx, spec["quote"], spec.get("occurrence"), spec.get("file")),
            spec,
        )
        if node.key in by_key:
            raise QuoteError(f"{fx.name}: duplicate node key {node.key}")
        by_key[node.key] = node
        res.nodes.append(node)
    for spec in exp.get("edges", []):
        sources = spec["source"] if isinstance(spec["source"], list) else [spec["source"]]
        targets = spec["target"] if isinstance(spec["target"], list) else [spec["target"]]
        for s in sources:
            for t in targets:
                ev = _evidence_items(fx, spec["evidence"], by_key, s, t)
                res.edges.append(ExpEdge(spec["relation"], s, t, spec["status"], ev, spec))
    for item in exp.get("uncovered", []):
        spec = {"quote": item} if isinstance(item, str) else dict(item)
        res.uncovered.append(locate(fx, spec["quote"], spec.get("occurrence"), spec.get("file")))
    return res
