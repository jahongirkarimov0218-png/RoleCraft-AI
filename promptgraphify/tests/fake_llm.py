"""A fake LLM adapter for contract tests: no network, scripted answers, records every call."""

from __future__ import annotations

import json
from collections.abc import Callable


class FakeAdapter:
    name = "fake"
    model = "fake-model-1"
    endpoint = "fake.invalid"
    timeout_s = 1.0

    def __init__(self, answer: str | dict | Callable[[str, str], str | dict] | Exception):
        self.answer = answer
        self.calls: list[tuple[str, str]] = []

    def complete(self, system: str, user: str) -> str:
        self.calls.append((system, user))
        a = self.answer
        if isinstance(a, Exception):
            raise a
        if callable(a):
            a = a(system, user)
        return a if isinstance(a, str) else json.dumps(a)


def ref_of(user: str, text: str) -> str:
    """The ``ref`` the analyzer gave to the existing node whose text is ``text`` (read from the request)."""
    nodes = json.loads(user)["nodes"]
    hits = [n["ref"] for n in nodes if n["text"] == text]
    assert len(hits) == 1, f"{text!r} matches {hits}"
    return hits[0]
