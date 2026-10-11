"""Local-first persistence behind a narrow interface (task constraint 5).

``GraphStore`` is the only thing the API and CLI know about. ``SqliteGraphStore`` implements it with the
standard library; a PostgreSQL implementation can replace it later without touching callers. A graph is
stored under its content-derived ``graph_id``, so saving the same analysis twice is a no-op.
"""

from __future__ import annotations

import os
import sqlite3
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Protocol

from . import graphjson
from .ir import GraphDocument

SCHEMA = """
CREATE TABLE IF NOT EXISTS graphs (
    id TEXT PRIMARY KEY,
    schema_version TEXT NOT NULL,
    analyzer_version TEXT NOT NULL,
    body TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ', 'now'))
) WITHOUT ROWID;
"""


class GraphStore(Protocol):
    def put(self, doc: GraphDocument) -> str: ...

    def get(self, graph_id: str) -> GraphDocument | None: ...

    def ids(self, limit: int = 100) -> list[str]: ...


class SqliteGraphStore:
    """File databases use one short-lived connection per call (safe across threads and processes; WAL lets
    readers run during a write and ``busy_timeout`` makes concurrent writers wait instead of failing).
    ``:memory:`` keeps one shared connection behind a lock."""

    def __init__(self, path: str | Path = ":memory:"):
        self.path = str(path)
        self._memory = self.path == ":memory:"
        self._lock = threading.Lock()
        self._shared: sqlite3.Connection | None = None
        if not self._memory:
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        with self._session() as con:
            con.executescript(SCHEMA)

    @contextmanager
    def _session(self) -> Iterator[sqlite3.Connection]:
        if self._memory:
            with self._lock:
                if self._shared is None:
                    self._shared = sqlite3.connect(":memory:", check_same_thread=False, isolation_level=None)
                    self._shared.row_factory = sqlite3.Row
                yield self._shared
            return
        con = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        try:
            con.row_factory = sqlite3.Row
            con.execute("PRAGMA journal_mode=WAL")
            con.execute("PRAGMA busy_timeout=30000")
            con.execute("PRAGMA synchronous=NORMAL")
            yield con
        finally:
            con.close()

    def put(self, doc: GraphDocument) -> str:
        body = graphjson.dumps(doc)
        with self._session() as con:
            con.execute("BEGIN IMMEDIATE")
            try:
                con.execute(
                    "INSERT OR IGNORE INTO graphs (id, schema_version, analyzer_version, body) VALUES (?, ?, ?, ?)",
                    (doc.graph_id, doc.schema_version, doc.analyzer_version, body),
                )
            except BaseException:
                con.execute("ROLLBACK")
                raise
            con.execute("COMMIT")
        return doc.graph_id

    def get(self, graph_id: str) -> GraphDocument | None:
        with self._session() as con:
            row = con.execute("SELECT body FROM graphs WHERE id = ?", (graph_id,)).fetchone()
        return graphjson.loads(row["body"]) if row else None

    def ids(self, limit: int = 100) -> list[str]:
        with self._session() as con:
            rows = con.execute("SELECT id FROM graphs ORDER BY created_at DESC, id LIMIT ?", (limit,)).fetchall()
        return [r["id"] for r in rows]


def default_db_path() -> Path:
    """``$PROMPTGRAPHIFY_DB`` or ``./promptgraphify-out/graphs.sqlite3`` (inside the working directory)."""
    return Path(os.environ.get("PROMPTGRAPHIFY_DB") or Path.cwd() / "promptgraphify-out" / "graphs.sqlite3")
