"""Signal words for the deterministic layer, loaded from JSON data files (en, ru, uz + common).

The JSON files are the only place where language-specific words and patterns live. Code asks
``SIGNALS.find("prohibition", text)``; it never contains a word list of its own.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from importlib import resources

LANGS = ("en", "ru", "uz")

# one-to-one (same length) replacement so match offsets stay valid: typographic apostrophes -> '
_APOSTROPHES = {ord(c): "'" for c in (chr(0x2019), chr(0x02BB), chr(0x02BC), chr(0x2018), "`")}


def fold(text: str) -> str:
    """Matching copy of ``text``: same length, apostrophe variants unified."""
    return text.translate(_APOSTROPHES)


@dataclass(frozen=True)
class Hit:
    category: str
    lang: str
    text: str
    start: int
    end: int
    groups: tuple[str | None, ...] = ()


class SignalSet:
    def __init__(self, per_lang: dict[str, dict], common: dict):
        self.per_lang = per_lang
        self.common = common
        self._patterns: dict[str, list[tuple[str, re.Pattern]]] = {}
        for lang, data in per_lang.items():
            for cat, value in data.items():
                if isinstance(value, list) and value and cat in _REGEX_CATEGORIES:
                    for pat in value:
                        self._patterns.setdefault(cat, []).append((lang, re.compile(pat, re.IGNORECASE)))
        self.verbs: dict[str, dict[str, set[str]]] = {
            lang: {
                "strict": {fold(v.lower()) for v in data.get("strict_verbs", [])},
                "task": {fold(v.lower()) for v in data.get("task_verbs", [])},
            }
            for lang, data in per_lang.items()
        }
        self.prefix_words = {fold(w) for d in per_lang.values() for w in d.get("prefix_words", [])}
        self.condition_words = {fold(w) for d in per_lang.values() for w in d.get("condition_words", [])}
        self.otherwise_words = [fold(w) for d in per_lang.values() for w in d.get("otherwise_words", [])]
        self.abbreviations = {fold(a.lower()) for d in per_lang.values() for a in d.get("abbreviations", [])}
        self.verb_position = {lang: d.get("verb_position", "start") for lang, d in per_lang.items()}
        self._common_re: dict[str, list[re.Pattern]] = {
            k: [re.compile(p, re.IGNORECASE) for p in common[k]]
            for k in ("agent_heading", "label_example", "label_context", "label_tools", "label_variables")
        }
        self.constraint_groups = {n.lower() for n in common["constraint_groups"]}
        self.example_names = {n.lower() for n in common["example_names"]}
        self.context_names = {n.lower() for n in common["context_names"]}
        self.stopwords = {fold(w) for w in common["stopwords"]}
        self.tool_names = {n.lower() for n in common["tool_names"]}
        self.tool_def_names = {n.lower() for n in common["tool_def_names"]}
        self.variable_names = {n.lower() for n in common["variable_names"]}
        self.tag_roles = {tag: role for role, tags in common["tag_roles"].items() for tag in tags}
        self.heading_roles = {name.lower(): role for role, names in common["heading_roles"].items() for name in names}

    # ------------------------------------------------------------------ regex categories
    def find(self, category: str, text: str) -> Hit | None:
        """Earliest match of any pattern of ``category`` in ``text`` (apostrophes folded)."""
        folded = fold(text)
        best: Hit | None = None
        for lang, pat in self._patterns.get(category, ()):
            m = pat.search(folded)
            if m and (best is None or m.start() < best.start):
                best = Hit(category, lang, text[m.start() : m.end()], m.start(), m.end(), m.groups())
        return best

    def find_all(self, category: str, text: str) -> list[Hit]:
        folded = fold(text)
        out: list[Hit] = []
        for lang, pat in self._patterns.get(category, ()):
            for m in pat.finditer(folded):
                out.append(Hit(category, lang, text[m.start() : m.end()], m.start(), m.end(), m.groups()))
        return sorted(out, key=lambda h: (h.start, h.end))

    def has(self, category: str, text: str) -> bool:
        return self.find(category, text) is not None

    # ------------------------------------------------------------------ common (structure) names
    def match_common(self, key: str, text: str) -> re.Match | None:
        folded = fold(text.strip())
        for pat in self._common_re[key]:
            m = pat.match(folded)
            if m:
                return m
        return None


_REGEX_CATEGORIES = {
    "identity", "hierarchy", "prohibition", "limit", "format", "output_spec", "sequence_words", "loop", "loop_back",
    "stop", "step_ref", "produce_before", "produce_after", "handoff", "call_verbs", "tool_mention", "vague",
    "injection", "success", "context_missing", "obligation", "modal_opener",
}  # fmt: skip


@lru_cache(maxsize=1)
def load_signals() -> SignalSet:
    base = resources.files(__package__)
    per_lang = {lang: json.loads((base / f"{lang}.json").read_text(encoding="utf-8")) for lang in LANGS}
    common = json.loads((base / "common.json").read_text(encoding="utf-8"))
    return SignalSet(per_lang, common)


SIGNALS = load_signals()
