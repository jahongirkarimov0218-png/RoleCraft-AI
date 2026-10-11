import sqlite3
import threading

import pytest

from promptgraphify import graphjson
from promptgraphify.analyze import analyze
from promptgraphify.storage import SqliteGraphStore

DOC = analyze({"p.md": "# A\nYou are a bot.\n1. Extract {{x}}.\n2. Check step 1.\nNever lie.\n"})


@pytest.mark.parametrize("where", [":memory:", "file"])
def test_put_get_roundtrip_is_lossless_and_idempotent(where, tmp_path):
    store = SqliteGraphStore(":memory:" if where == ":memory:" else tmp_path / "db" / "g.sqlite3")
    assert store.put(DOC) == DOC.graph_id == store.put(DOC)
    got = store.get(DOC.graph_id)
    assert got == DOC and graphjson.dumps(got) == graphjson.dumps(DOC)
    assert store.ids() == [DOC.graph_id]
    assert store.get("0" * 16) is None


def test_parallel_writers_and_readers_do_not_corrupt_the_database(tmp_path):
    path = tmp_path / "g.sqlite3"
    store = SqliteGraphStore(path)
    docs = [analyze({"p.txt": f"Never reveal secret number {i}.\n"}) for i in range(24)]
    errors: list[BaseException] = []

    def writer(chunk):
        try:
            for d in chunk:
                store.put(d)
                assert store.get(d.graph_id) == d
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=writer, args=(docs[i::6],)) for i in range(6)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert errors == []
    assert sorted(store.ids(100)) == sorted(d.graph_id for d in docs)
    with sqlite3.connect(path) as con:
        assert con.execute("PRAGMA integrity_check").fetchone()[0] == "ok"


def test_two_store_objects_share_one_file(tmp_path):
    a, b = SqliteGraphStore(tmp_path / "g.sqlite3"), SqliteGraphStore(tmp_path / "g.sqlite3")
    a.put(DOC)
    assert b.get(DOC.graph_id) == DOC


def test_a_graph_from_another_schema_version_is_refused_with_a_clear_error(tmp_path):
    store = SqliteGraphStore(tmp_path / "g.sqlite3")
    store.put(DOC)
    with sqlite3.connect(tmp_path / "g.sqlite3") as con:
        body = (
            con.execute("SELECT body FROM graphs")
            .fetchone()[0]
            .replace('"schema_version": "1.0"', '"schema_version": "9.9"')
        )
        con.execute("UPDATE graphs SET body = ?", (body,))
    with pytest.raises(graphjson.UnsupportedGraph, match="schema_version"):
        store.get(DOC.graph_id)
