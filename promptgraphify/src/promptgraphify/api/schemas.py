"""Request / response / error schemas of the HTTP API. These models are the contract: OpenAPI is
generated from them and the web client's TypeScript types are generated from OpenAPI."""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..ir import GraphDocument

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
        "configured provider (see /api/health).",
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
    llm_enabled: bool = Field(description="True only if an LLM provider is configured and Layer B is allowed.")
    llm_provider: str | None = None
