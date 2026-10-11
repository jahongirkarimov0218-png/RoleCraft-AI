"""Request / response / error schemas of the HTTP API. These models are the contract: OpenAPI is
generated from them and the web client's TypeScript types are generated from OpenAPI."""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ..ir import Diagnostic, Edge, GraphDocument, Node

_BAD_PATH = re.compile(r"[\x00-\x1f\x7f\\]")


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


def normalize_input_path(raw: str) -> str:
    """A relative POSIX path without ``..``, drive letters, control characters or backslashes."""
    if not raw or len(raw) > 255 or _BAD_PATH.search(raw):
        raise ValueError("path must be 1-255 characters without control characters or backslashes")
    if raw.startswith("/") or re.match(r"^[A-Za-z]:", raw):
        raise ValueError("path must be relative")
    parts = [p for p in raw.split("/") if p not in ("", ".")]
    if not parts or any(p == ".." for p in parts):
        raise ValueError("path must stay inside the project (no '..')")
    return "/".join(parts)


class FileInput(_Strict):
    path: str = Field(description="Relative POSIX path used as the source name, e.g. 'agents/planner.md'.")
    text: str = Field(description="File content exactly as it should be analysed (not normalised).")

    @field_validator("path")
    @classmethod
    def _path(cls, value: str) -> str:
        return normalize_input_path(value)


class AnalyzeRequest(_Strict):
    files: list[FileInput] = Field(min_length=1, max_length=200)
    layer_b: bool = Field(
        default=False,
        description="Enable the optional LLM layer. Off by default; when on, the prompt text is sent to the "
        "configured provider (see /api/health). 503 llm_unavailable if no provider is configured.",
    )


class AnalyzeResponse(_Strict):
    graph_id: str
    graph: GraphDocument


class ErrorDetail(_Strict):
    field: str | None = None
    message: str


class ErrorBody(_Strict):
    code: Literal[
        "invalid_request",
        "input_too_large",
        "no_input",
        "duplicate_path",
        "invalid_text",
        "not_found",
        "unsupported_schema",
        "timeout",
        "internal_error",
        "internal_invariant_failed",
        "llm_unavailable",
    ]
    message: str
    details: list[ErrorDetail] | None = None


class ErrorResponse(_Strict):
    error: ErrorBody


class Health(_Strict):
    status: Literal["ok"]
    version: str
    schema_version: str
    llm_enabled: bool = Field(
        description="True if an LLM provider is configured, i.e. a request may ask for the optional LLM layer. "
        "The layer itself is off unless a request sets layer_b."
    )
    llm_provider: str | None
    llm_model: str | None
    llm_endpoint: str | None = Field(description="Host (and port) the prompt text is sent to when layer_b is on.")


class NodeDetail(_Strict):
    node: Node
    incoming: list[Edge]
    outgoing: list[Edge]
    diagnostics: list[Diagnostic]


class ViolationOut(_Strict):
    code: str
    message: str
    subject: str | None


class SeverityCounts(_Strict):
    error: int
    warning: int
    info: int


class ValidateRequest(_Strict):
    """Either analyse ``files`` or check an existing ``graph`` document (exactly one)."""

    files: list[FileInput] | None = Field(default=None, min_length=1, max_length=200)
    graph: GraphDocument | None = None

    @model_validator(mode="after")
    def _one_of(self) -> ValidateRequest:
        if (self.files is None) == (self.graph is None):
            raise ValueError("give exactly one of 'files' or 'graph'")
        return self


class ValidateResponse(_Strict):
    ok: bool = Field(description="False if the graph is invalid or any diagnostic has severity 'error'.")
    graph_id: str | None
    violations: list[ViolationOut]
    diagnostics: list[Diagnostic]
    counts: SeverityCounts


class DiffSide(_Strict):
    """One side of a comparison: a stored graph (``graph_id``) or files to analyse (exactly one)."""

    graph_id: str | None = Field(default=None, pattern=r"^[0-9a-f]{16}$")
    files: list[FileInput] | None = Field(default=None, min_length=1, max_length=200)

    @model_validator(mode="after")
    def _one_of(self) -> DiffSide:
        if (self.graph_id is None) == (self.files is None):
            raise ValueError("give exactly one of 'graph_id' or 'files'")
        return self


class DiffRequest(_Strict):
    old: DiffSide
    new: DiffSide
