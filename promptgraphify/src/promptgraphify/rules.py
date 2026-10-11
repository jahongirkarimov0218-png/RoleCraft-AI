"""Registry of analyzer rules. Mirrors the table in docs/ANALYSIS_SPEC.md §7 (a test keeps the two in
sync). A rule that is listed here but not yet implemented is tracked in docs/STATUS.md."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .ir import Certainty, Detection, Severity


@dataclass(frozen=True)
class Rule:
    id: str
    severity: Severity
    detection: Detection
    # "proven": always follows from the source/graph; "probable": heuristic or LLM;
    # "mixed": proven when only EXTRACTED edges are involved, probable otherwise.
    certainty: Certainty | Literal["mixed"]
    summary: str


def _r(id_: str, sev: Severity, det: Detection, cert, summary: str) -> tuple[str, Rule]:
    return id_, Rule(id_, sev, det, cert, summary)


RULES: dict[str, Rule] = dict(
    [
        _r("input.empty", "error", "deterministic", "proven", "no non-whitespace text"),
        _r("parse.malformed", "warning", "deterministic", "proven", "broken syntax"),
        _r("template.malformed", "warning", "deterministic", "proven", "nested or unbalanced placeholder"),
        _r("variable.undeclared", "warning", "deterministic", "proven", "variable used, never defined"),
        _r("variable.unused", "info", "deterministic", "proven", "variable declared, never used"),
        _r("tool.undefined", "warning", "heuristic", "probable", "call-like reference to an undefined tool"),
        _r("tool.unused", "info", "deterministic", "proven", "tool defined, never referenced"),
        _r(
            "tool.permission_mismatch",
            "error",
            "heuristic",
            "probable",
            "a constraint forbids a tool a task calls",
        ),
        _r("dependency.cycle", "error", "deterministic", "mixed", "cycle in the execution DAG"),
        _r("dependency.unresolved", "error", "deterministic", "proven", "names a step that does not exist"),
        _r(
            "task.unreachable",
            "warning",
            "deterministic",
            "proven",
            "task blocked by a cycle or unresolved dependency",
        ),
        _r("node.orphan", "info", "deterministic", "proven", "node without any edge"),
        _r("instruction.duplicate", "info", "deterministic", "proven", "same normalised text twice"),
        _r("constraint.conflict", "warning", "heuristic", "probable", "contradictory instructions"),
        _r("role.conflict", "warning", "heuristic", "probable", "two identities in one scope"),
        _r("instruction.ambiguous", "info", "heuristic", "probable", "vague wording without a criterion"),
        _r("output.contract_missing", "info", "heuristic", "probable", "no output specification"),
        _r("success.criteria_unclear", "info", "heuristic", "probable", "no success / acceptance wording"),
        _r("context.unavailable", "warning", "heuristic", "probable", "refers to context nothing supplies"),
        _r("injection.indicator", "warning", "heuristic", "probable", "override / exfiltration phrase"),
        _r("loop.no_stop_condition", "warning", "heuristic", "probable", "repetition without a stop clause"),
    ]
)
