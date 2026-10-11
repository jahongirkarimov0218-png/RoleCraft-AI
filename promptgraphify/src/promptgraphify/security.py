"""Single entry point for sanitising external text (labels now; paths, limits and uploads in M5).

Labels are *data*. They are stripped of control and bidi-override characters and length-capped here;
HTML escaping is the job of each renderer (React escapes by default, ``graph.html`` uses textContent).
"""

from __future__ import annotations

import re

MAX_LABEL_LEN = 200

# C0/C1 controls, line/paragraph separators, bidi embedding/override/isolate marks, zero-width marks
# that are used for spoofing. Any run of them (and of whitespace) collapses to one space.
_UNSAFE_OR_SPACE = re.compile(
    "[\\s\\x00-\\x1f\\x7f-\\x9f\\u2028\\u2029\\u202a-\\u202e\\u2066-\\u2069\\u200b-\\u200f\\ufeff]+"
)


def sanitize_label(text: str | None) -> str:
    """One-line, control-free, at most ``MAX_LABEL_LEN`` code points (a trailing ``…`` marks a cut)."""
    if not text:
        return ""
    cleaned = _UNSAFE_OR_SPACE.sub(" ", text).strip()
    if len(cleaned) > MAX_LABEL_LEN:
        cleaned = cleaned[: MAX_LABEL_LEN - 1].rstrip() + "…"
    return cleaned


def is_clean_label(text: str) -> bool:
    """True if ``text`` is non-empty and unchanged by :func:`sanitize_label`."""
    return bool(text) and text == sanitize_label(text)
