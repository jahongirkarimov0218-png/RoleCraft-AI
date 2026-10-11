"""Measure the analysis pipeline at several sizes: ``python -m tests.measure_perf`` (from the project root).
Prints a Markdown table; numbers depend on the machine, so they are reported with it, never asserted tightly."""

from __future__ import annotations

import os
import platform
import sys
import time

from promptgraphify import graphjson
from promptgraphify.analyze import analyze
from promptgraphify.exporters import to_graphml, to_html, to_report, to_svg
from promptgraphify.ir import GraphDocument
from promptgraphify.validate import validate_document

from .synthetic import synthetic_prompt

SIZES = (60, 150, 300, 600, 1200)
HEADER = (
    "| units | chars | nodes | edges | dag vertices | analyze | validate | graph.json | html | report | svg | graphml "
    "| json size |"
)


def best(fn, repeat: int = 3) -> float:
    times = []
    for _ in range(repeat):
        t = time.perf_counter()
        fn()
        times.append(time.perf_counter() - t)
    return min(times)


def measure(units: int) -> list:
    text = synthetic_prompt(units)
    doc: GraphDocument = analyze({"p.md": text})
    size = len(graphjson.dumps(doc)) / 1e6
    return [
        units, len(text), len(doc.nodes), len(doc.edges), len(doc.dag.vertices),
        best(lambda: analyze({"p.md": text})),
        best(lambda: validate_document(doc)),
        best(lambda: graphjson.dumps(doc)),
        best(lambda: to_html(doc), 2),
        best(lambda: to_report(doc)),
        best(lambda: to_svg(doc, "graph"), 2),
        best(lambda: to_graphml(doc), 2),
        f"{size:.2f} MB",
    ]  # fmt: skip


def main() -> None:
    print(f"python {platform.python_version()} on {platform.platform()} ({os.cpu_count()} CPUs); best of 3, seconds\n")
    print(HEADER)
    print("|" + "---|" * 13)
    for n in SIZES:
        print("| " + " | ".join(f"{v:.3f}" if isinstance(v, float) else str(v) for v in measure(n)) + " |")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
