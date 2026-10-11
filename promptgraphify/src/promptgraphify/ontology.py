"""Closed ontology: six node types and eleven relations (task constraint 6).

Nothing outside these tables may be added silently. If the ontology turns out to be too small, write
the gap into docs/DECISIONS.md as a proposal; do not extend the Literals below.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import product
from typing import Literal, get_args

NodeType = Literal[
    "SystemNode",
    "TaskNode",
    "ContextNode",
    "ConstraintNode",
    "ToolNode",
    "ExampleNode",
]
Relation = Literal[
    "DEPENDS_ON",
    "CONSTRAINS",
    "PROVIDES_CONTEXT",
    "CALLS_TOOL",
    "PRODUCES",
    "REFERENCES",
    "OVERRIDES",
    "CONFLICTS_WITH",
    "PRECEDES",
    "EXEMPLIFIES",
    "CONDITIONALLY_EXECUTES",
]
EdgeStatus = Literal["EXTRACTED", "INFERRED", "AMBIGUOUS"]

NODE_TYPES: tuple[str, ...] = get_args(NodeType)
RELATIONS: tuple[str, ...] = get_args(Relation)
EDGE_STATUSES: tuple[str, ...] = get_args(EdgeStatus)

TYPE_CODES: dict[str, str] = {
    "SystemNode": "sys",
    "TaskNode": "task",
    "ContextNode": "ctx",
    "ConstraintNode": "con",
    "ToolNode": "tool",
    "ExampleNode": "ex",
}

_SYS, _TASK, _CTX, _CON, _TOOL, _EX = NODE_TYPES


@dataclass(frozen=True)
class RelationSpec:
    """Direction, allowed (source type, target type) pairs and DAG projection of one relation.

    Reading rule: ``source RELATION target`` (``Task DEPENDS_ON Context`` = the task depends on the
    context). ``dag`` is how the relation is projected into the Execution DAG: ``"forward"`` keeps
    the arrow source -> target, ``"reversed"`` flips it (DEPENDS_ON points the opposite way to
    PRECEDES), ``None`` means the relation carries no execution order.
    """

    name: str
    pairs: frozenset[tuple[str, str]]
    allowed_status: frozenset[str]
    symmetric: bool
    dag: Literal["forward", "reversed"] | None
    description: str


def _pairs(sources: tuple[str, ...], targets: tuple[str, ...]) -> set[tuple[str, str]]:
    return set(product(sources, targets))


_ALL_STATUS = frozenset(EDGE_STATUSES)
_NOT_EXTRACTED = frozenset({"INFERRED", "AMBIGUOUS"})

RELATION_TABLE: dict[str, RelationSpec] = {
    spec.name: spec
    for spec in (
        RelationSpec(
            "DEPENDS_ON",
            frozenset(_pairs((_TASK,), (_TASK, _CTX)) | _pairs((_TOOL,), (_CTX,))),
            _ALL_STATUS,
            False,
            "reversed",
            "Source needs the target (a step, an input) before it can run.",
        ),
        RelationSpec(
            "CONSTRAINS",
            frozenset(_pairs((_CON,), (_TASK, _TOOL, _CTX, _SYS))),
            _ALL_STATUS,
            False,
            None,
            "Source restricts how the target may behave or be used.",
        ),
        RelationSpec(
            "PROVIDES_CONTEXT",
            frozenset(_pairs((_CTX,), (_TASK, _TOOL))),
            _ALL_STATUS,
            False,
            None,
            "Source supplies background information to the target (not a hard input).",
        ),
        RelationSpec(
            "CALLS_TOOL",
            frozenset(_pairs((_TASK,), (_TOOL,))),
            _ALL_STATUS,
            False,
            "forward",
            "The task invokes the tool.",
        ),
        RelationSpec(
            "PRODUCES",
            frozenset(_pairs((_TASK, _TOOL), (_CTX,))),
            _ALL_STATUS,
            False,
            "forward",
            "Source writes the target value (output variable, tool result).",
        ),
        RelationSpec(
            "REFERENCES",
            frozenset(_pairs(NODE_TYPES, NODE_TYPES)),
            _ALL_STATUS,
            False,
            None,
            "Source names the target in its text without a stronger relation.",
        ),
        RelationSpec(
            "OVERRIDES",
            frozenset(_pairs((_SYS, _CON, _TASK), (_SYS, _CON, _TASK))),
            _ALL_STATUS,
            False,
            None,
            "Source states precedence over the target.",
        ),
        RelationSpec(
            "CONFLICTS_WITH",
            frozenset(_pairs((_SYS, _CON, _TASK), (_SYS, _CON, _TASK))),
            _NOT_EXTRACTED,
            True,
            None,
            "Source and target give incompatible instructions. Symmetric; source = earlier span. "
            "Never EXTRACTED: a conflict is a semantic judgement, not an explicit reference.",
        ),
        RelationSpec(
            "PRECEDES",
            frozenset(_pairs((_TASK,), (_TASK,))),
            _ALL_STATUS,
            False,
            "forward",
            "Source must complete before the target starts.",
        ),
        RelationSpec(
            "EXEMPLIFIES",
            frozenset(_pairs((_EX,), (_TASK, _CON, _TOOL))),
            _ALL_STATUS,
            False,
            None,
            "The example illustrates the target.",
        ),
        RelationSpec(
            "CONDITIONALLY_EXECUTES",
            frozenset(_pairs((_CTX, _TASK), (_TASK,))),
            _ALL_STATUS,
            False,
            "forward",
            "The target runs only if the source (the gate named in the condition) holds.",
        ),
    )
}

assert tuple(RELATION_TABLE) == RELATIONS, "relation table must cover every relation exactly once"


def pair_allowed(relation: str, source_type: str, target_type: str) -> bool:
    spec = RELATION_TABLE.get(relation)
    return spec is not None and (source_type, target_type) in spec.pairs
