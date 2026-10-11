"""Sentence classification (ANALYSIS_SPEC §3.5). Pure function of the sentence text and the signal
data; nothing here knows about files, containers or fixtures."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .ontology import NodeType
from .signals import SIGNALS, Hit, fold
from .text import WORD, words

# An opener may follow prefix words ("Then you must ...", "Затем вам нужно ..."). Real prompts put at most two or three
# there; the bound keeps a sentence made of thousands of prefix words linear.
MAX_PREFIX_WORDS = 3
_LEADING_SEPARATORS = re.compile(r"^[\s,]+")


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
    return (
        len(word) > 4
        and word.endswith("ly")
        and not any(word in v["strict"] or word in v["task"] for v in SIGNALS.verbs.values())
    )


def _is_question(text: str) -> bool:
    return text.rstrip().endswith("?")


def _opener(category: str, clause: str) -> tuple[str, Hit | None]:
    """``clause`` after a leading opener of ``category`` ("You must", "Ваша задача —", "Vazifangiz —", "Ответ должен
    быть"), also when up to MAX_PREFIX_WORDS prefix words precede it, and the opener. A question is never an
    instruction, so it has no opener. Only the lookup is shortened; the node keeps the whole sentence."""
    if _is_question(clause):
        return clause, None
    body = clause.lstrip()
    starts = [0]
    for m in WORD.finditer(fold(body)):
        if len(starts) > MAX_PREFIX_WORDS or m.group(0).lower() not in SIGNALS.prefix_words:
            break
        starts.append(m.end())
    for start in starts:
        rest = _LEADING_SEPARATORS.sub("", body[start:], count=1)
        if hit := SIGNALS.match_start(category, rest):
            return rest[hit.end :], hit
    return clause, None


def _without_closer(text: str) -> tuple[str, bool]:
    """``text`` without a trailing task closer of a verb-final language, and whether there was one. A 2nd-person closer
    ("...ishingiz kerak", "...ishga majbursiz") names the model as the agent. An impersonal one ("...ish kerak",
    "... talab qilinadi") counts only when the sentence does not first name someone else ("Menga ...",
    "Ertaga menga ...", "Foydalanuvchi ..."): then it states their need or duty, not an instruction to the model."""
    if _is_question(text):
        return text, False
    body = text.strip()
    hit = SIGNALS.match_end("task_closers", body)
    if hit is None and not SIGNALS.match_start("closer_blockers", body):
        hit = SIGNALS.match_end("impersonal_closers", body)
    return (body[: hit.start], True) if hit else (text, False)


def _lookup(word: str, lang: str, nonfinite: bool) -> Verb | None:
    """``word`` as a verb of ``lang``. Non-finite forms (infinitive, verbal noun) count only after an opener or a
    closer: on their own ("Перевести текст.") they are not read as instructions, so earlier results do not change."""
    v = SIGNALS.verbs[lang]
    if word in v["strict"] or (nonfinite and word in v["strict_nonfinite"]):
        return Verb(word, True, lang)
    if word in v["task"] or (nonfinite and word in v["task_nonfinite"]):
        return Verb(word, False, lang)
    return None


def find_verb(text: str) -> Verb | None:
    candidates = _clause_candidates(text)
    opened = False
    for clause in candidates:
        body, hit = _opener("task_openers", clause)
        opened = opened or hit is not None
        toks = words(body)
        i = 0
        while i < len(toks) and _skippable(toks[i][0]):
            i += 1
        if i < len(toks):
            for lang, pos in SIGNALS.verb_position.items():
                if pos == "start" and (verb := _lookup(toks[i][0], lang, hit is not None)):
                    return verb
    body, closed = _without_closer(text)
    # fold first: a typographic apostrophe (o’qish) must not split the word the way the raw text would
    toks = [w for w, _, _ in words(fold(body))]
    for lang, pos in SIGNALS.verb_position.items():
        if pos != "end":
            continue
        for n in (2, 1):
            if len(toks) >= n and (verb := _lookup(" ".join(toks[-n:]), lang, opened or closed)):
                return verb
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
    output = next((hit for c in _clause_candidates(stripped) if (hit := _opener("constraint_openers", c)[1])), None)
    if output:
        return Classification(
            "ConstraintNode",
            0.8,
            "output_obligation",
            f"Obligation on the output (signal: {output.text[:40]!r})",
            [output.text],
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
