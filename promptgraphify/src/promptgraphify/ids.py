"""Stable node/edge identifiers (ANALYSIS_SPEC §8, decision D-004).

IDs depend on structure and content, never on offsets: inserting a line elsewhere in the prompt does
not change the IDs of other units. All normalisation lives in this module on purpose; a second copy
of the recipe is exactly how ID drift bugs start.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from collections.abc import Iterable

from .ontology import TYPE_CODES

_LIST_MARKER = re.compile(r"^\s*(?:[-*+•–—]|\(?\d{1,3}[.)]|\(?[a-zA-Z][.)])\s+")
_NON_WORD = re.compile(r"[^\w]+", re.UNICODE)
_WS = re.compile(r"\s+")

MAX_KEY_SLUG = 40


def normalize_text(text: str) -> str:
    """NFKC, casefold, list marker removed, whitespace collapsed. Idempotent."""
    cur = text
    for _ in range(4):  # casefold and NFKC do not commute; iterate to a fixpoint
        nxt = unicodedata.normalize("NFKC", cur.casefold())
        if nxt == cur:
            break
        cur = nxt
    cur = _LIST_MARKER.sub("", cur, count=1)
    return _WS.sub(" ", cur).strip()


def slugify(text: str) -> str:
    """Unicode-aware slug: letters/digits/underscore are kept, everything else becomes ``-``."""
    return _NON_WORD.sub("-", normalize_text(text)).strip("-")


def text_digest(text: str, length: int = 8) -> str:
    return hashlib.sha256(normalize_text(text).encode("utf-8")).hexdigest()[:length]


def _path_part(path: Iterable[str]) -> str:
    parts = [s for s in (slugify(p) for p in path) if s]
    return ".".join(parts) if parts else "-"


def named_key(name: str) -> str:
    """Key for things identified by name (variables, tools): the slug of the name."""
    return slugify(name)[:MAX_KEY_SLUG].strip("-") or text_digest(name)


def text_key(text: str) -> str:
    """Key for free-text units: slug of the first four words + 8 hex digits of the text hash."""
    words = normalize_text(text).split(" ")[:4]
    lead = _NON_WORD.sub("-", " ".join(words)).strip("-")[:MAX_KEY_SLUG].strip("-")
    digest = text_digest(text)
    return f"{lead}-{digest}" if lead else digest


def node_id(node_type: str, path: Iterable[str], key: str) -> str:
    return f"{TYPE_CODES[node_type]}:{_path_part(path)}:{key}"


def disambiguate(base_ids: list[str]) -> list[str]:
    """Identical base IDs get ``~2``, ``~3`` … in document order; the first keeps the plain ID."""
    seen: dict[str, int] = {}
    result: list[str] = []
    for base in base_ids:
        seen[base] = seen.get(base, 0) + 1
        result.append(base if seen[base] == 1 else f"{base}~{seen[base]}")
    return result


def edge_id(relation: str, source: str, target: str, ordinal: int = 1) -> str:
    raw = f"{relation}|{source}|{target}|{ordinal}".encode()
    return "e_" + hashlib.sha256(raw).hexdigest()[:12]
