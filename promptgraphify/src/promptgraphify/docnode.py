"""A tiny format-neutral tree for YAML and JSON documents, with raw offsets.

Both front-ends (``jsonscan``, ``yamlscan``) produce ``DNode`` trees; ``structured.py`` walks them. A
string node remembers where each *decoded* character came from in the raw text (``map_start`` /
``map_end``), so a sentence found in the decoded text can be turned back into an exact raw span.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class DNode:
    kind: str  # "map" | "seq" | "str" | "scalar"
    start: int  # raw offsets, half-open
    end: int
    value: str | None = None  # decoded text of a string / scalar
    items: list[tuple[DNode | None, DNode]] = field(default_factory=list)  # map: (key, value); seq: (None, value)
    map_start: list[int] | None = None  # str: raw start of every decoded character (None = unknown)
    map_end: list[int] | None = None
    style: str = ""  # YAML scalar style: "", "'", '"', "|", ">"; JSON strings use '"'

    @property
    def is_prose(self) -> bool:
        """A string with at least one whitespace-separated word pair: configuration tokens such as
        ``ticket-triage`` or ``json`` are values, not prose."""
        return self.kind == "str" and self.value is not None and len(self.value.split()) > 1

    def key_text(self) -> str:
        return (self.value or "").strip()
