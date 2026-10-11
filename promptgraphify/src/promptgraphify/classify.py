"""Sentence classification (ANALYSIS_SPEC §3.5). Pure function of the sentence text and the signal
data; nothing here knows about files, containers or fixtures."""

from __future__ import annotations

from dataclasses import dataclass, field

from .ontology import NodeType
from .signals import SIGNALS, fold
from .text import words


@dataclass
class Verb:
    word: str
    strict: bool
    lang: str


@dataclass
class Classification:
    type: NodeType
    confidence: float
    rule: str  # becomes extraction_method "deterministic:<rule>"
    description: str
    signals: list[str] = field(default_factory=list)
    mixed: bool = False
    verb: str | None = None
    embedded: list[str] = field(default_factory=list)


def _clause_candidates(text: str) -> list[str]:
    """The sentence itself, preceded by the clause after its first comma when the sentence opens with a
    condition word, a gerund / ``to`` / ``by`` phrase or a prefix word ("If x, do y" -> "do y")."""
    toks = words(text)
    cands = [text]
    if toks and "," in text:
        first = toks[0][0]
        opener = first in SIGNALS.condition_words or _skippable(first) or first in ("to", "by")
        if opener or first.endswith("ing"):
            cands.insert(0, text[text.index(",") + 1 :])
    return cands


def _skippable(word: str) -> bool:
    """A word that may stand before the imperative verb: a prefix word ("please", "then") or an English manner
    adverb ("briefly summarize", "carefully review"). A word ending in -ly is an adverb unless it is a known verb
    ("reply", "apply", "comply", "rely")."""
    if word in SIGNALS.prefix_words:
        return True
    return len(word) > 4 and word.endswith("ly") and not any(
        word in v["strict"] or word in v["task"] for v in SIGNALS.verbs.values()
    )


def find_verb(text: str) -> Verb | None:
    for clause in _clause_candidates(text):
        toks = words(clause)
        i = 0
        while i < len(toks) and _skippable(toks[i][0]):
            i += 1
        if i < len(toks):
            w = toks[i][0]
            for lang, pos in SIGNALS.verb_position.items():
                if pos != "start":
                    continue
                if w in SIGNALS.verbs[lang]["strict"]:
                    return Verb(w, True, lang)
                if w in SIGNALS.verbs[lang]["task"]:
                    return Verb(w, False, lang)
    toks = [w for w, _, _ in words(text)]
    for lang, pos in SIGNALS.verb_position.items():
        if pos != "end":
            continue
        for n in (2, 1):
            tail = " ".join(toks[-n:]) if len(toks) >= n else None
            if tail is None:
                continue
            if tail in SIGNALS.verbs[lang]["strict"]:
                return Verb(tail, True, lang)
            if tail in SIGNALS.verbs[lang]["task"]:
                return Verb(tail, False, lang)
    return None


def classify(text: str) -> Classification | None:
    """Type of one sentence, or ``None`` when no signal applies (the sentence stays uncovered)."""
    stripped = text.strip()
    hit = SIGNALS.find("identity", stripped)
    if hit and hit.start == 0:
        return Classification(
            "SystemNode", 0.8, "identity", f"Identity statement (pattern: {hit.text[:30]!r})", [hit.text]
        )
    hit = SIGNALS.find("hierarchy", stripped)
    if hit:
        return Classification(
            "SystemNode", 0.8, "hierarchy", f"Instruction-hierarchy statement ({hit.text!r})", [hit.text]
        )

    verb = find_verb(stripped)
    prohibition = SIGNALS.find("prohibition", stripped)
    limit = SIGNALS.find_all("limit", stripped)
    fmt = SIGNALS.find_all("format", stripped)
    embedded = [h.text for h in (*limit, *fmt)]

    if prohibition:
        mixed = bool(verb and verb.strict)
        return Classification(
            "ConstraintNode",
            0.6 if mixed else 0.8,
            "prohibition",
            f"Negative constraint (signal: {prohibition.text!r})",
            [prohibition.text],
            mixed=mixed,
            verb=verb.word if verb else None,
        )
    if verb and verb.strict:
        return Classification(
            "TaskNode",
            0.8,
            "task_verb",
            f"Task (imperative verb: {verb.word!r})",
            [verb.word],
            verb=verb.word,
            embedded=embedded,
        )
    if limit or fmt:
        first = (limit or fmt)[0]
        kind = "limit" if limit else "format"
        return Classification(
            "ConstraintNode",
            0.8,
            kind,
            f"{kind.capitalize()} constraint (signal: {first.text!r})",
            [h.text for h in (*limit, *fmt)],
            verb=verb.word if verb else None,
        )
    if verb:
        return Classification(
            "TaskNode",
            0.8,
            "task_verb",
            f"Task (imperative verb: {verb.word!r})",
            [verb.word],
            verb=verb.word,
        )
    return None


def condition_clause(text: str) -> tuple[int, int] | None:
    """Offsets (within ``text``) of an explicit condition clause: "If x" in "If x, do y", or
    "when appropriate" in "Do y when appropriate."."""
    toks = words(text)
    if not toks:
        return None
    if toks[0][0] in SIGNALS.condition_words:
        end = text.find(",")
        return (toks[0][1], end if end != -1 else len(text.rstrip(" .!?;")))
    for w, a, _ in toks[1:]:
        if w in SIGNALS.condition_words:
            return (a, len(text.rstrip(" .!?;")))
    return None


def loop_info(text: str) -> dict | None:
    """``{"stop_condition": str | None}`` if the sentence repeats something, else ``None``."""
    if not SIGNALS.has("loop", text):
        return None
    stop = SIGNALS.find("stop", text)
    if stop:
        return {"stop_condition": text[stop.start :].rstrip(" .!?;")}
    return {"stop_condition": None}


def is_otherwise(text: str) -> bool:
    folded = fold(text.strip()).lower()
    return any(folded.startswith(w) for w in SIGNALS.otherwise_words)
