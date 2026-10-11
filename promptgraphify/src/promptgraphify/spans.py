"""Span model and offset-unit conversion (decision D-003).

Canonical unit: Unicode code points (Python ``str`` indices), half-open ``[start, end)``, measured on
the raw source text. JavaScript strings and Monaco use UTF-16 code units; the only place that
converts is ``cp_to_utf16`` / ``utf16_to_cp`` here and the mirrored helper in the web client.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Span(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    start: int = Field(ge=0)
    end: int = Field(ge=0)

    @model_validator(mode="after")
    def _ordered(self) -> Span:
        if self.end < self.start:
            raise ValueError(f"span end {self.end} is before start {self.start}")
        return self

    def __len__(self) -> int:
        return self.end - self.start

    def text(self, source: str) -> str:
        return source[self.start : self.end]

    def within(self, source: str) -> bool:
        return self.end <= len(source)

    def overlaps(self, other: Span) -> bool:
        return self.start < other.end and other.start < self.end

    def contains(self, other: Span) -> bool:
        return self.start <= other.start and other.end <= self.end


def cp_to_utf16(text: str, cp_offset: int) -> int:
    """UTF-16 code-unit offset of the code point at ``cp_offset`` (0 <= cp_offset <= len(text))."""
    if not 0 <= cp_offset <= len(text):
        raise ValueError(f"offset {cp_offset} outside text of {len(text)} code points")
    return cp_offset + sum(1 for ch in text[:cp_offset] if ord(ch) > 0xFFFF)


def utf16_to_cp(text: str, u16_offset: int) -> int:
    """Inverse of :func:`cp_to_utf16`; raises if the offset splits a surrogate pair."""
    if u16_offset < 0:
        raise ValueError("negative offset")
    units = 0
    for cp, ch in enumerate(text):
        if units == u16_offset:
            return cp
        if units > u16_offset:
            raise ValueError(f"UTF-16 offset {u16_offset} splits a surrogate pair")
        units += 2 if ord(ch) > 0xFFFF else 1
    if units == u16_offset:
        return len(text)
    raise ValueError(f"UTF-16 offset {u16_offset} outside text of {units} code units")
