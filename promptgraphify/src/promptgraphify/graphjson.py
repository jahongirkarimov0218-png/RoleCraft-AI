"""graph.json: canonical serialisation and a reader that refuses documents it cannot trust."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from pydantic import ValidationError

from .ir import SCHEMA_VERSION, GraphDocument
from .validate import GraphInvalid, validate_document


class UnsupportedGraph(ValueError):
    """graph.json has a different schema_version, is not JSON, or does not match the schema."""


def dumps(doc: GraphDocument) -> str:
    """Canonical text: sorted keys, 2-space indent, no ASCII escaping, trailing newline.
    Same document -> same bytes (no timestamps or host data live in the document)."""
    return json.dumps(doc.model_dump(mode="json"), sort_keys=True, indent=2, ensure_ascii=False) + "\n"


def loads(text: str) -> GraphDocument:
    try:
        raw = json.loads(text)
    except ValueError as exc:
        raise UnsupportedGraph(f"graph.json is not valid JSON: {exc}") from exc
    if not isinstance(raw, dict):
        raise UnsupportedGraph("graph.json must contain a JSON object")
    version = raw.get("schema_version")
    if version != SCHEMA_VERSION:
        raise UnsupportedGraph(
            f"graph.json has schema_version {version!r}; this build reads {SCHEMA_VERSION!r}. "
            "Re-run `promptgraphify analyze` with the current version to regenerate it."
        )
    try:
        doc = GraphDocument.model_validate(raw)
    except ValidationError as exc:
        raise UnsupportedGraph(
            f"graph.json does not match the schema: {exc.error_count()} error(s), first: {exc.errors()[0]['msg']}"
        ) from exc
    violations = validate_document(doc)
    if violations:
        raise GraphInvalid(violations)
    return doc


def write_atomic(path: str | Path, text: str) -> None:
    """Write ``text`` to ``path`` so a reader never sees a half-written file (temp file + rename)."""
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=target.parent, prefix=f".{target.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, target)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
