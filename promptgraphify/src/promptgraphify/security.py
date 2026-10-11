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
    "[\\s\\x00-\\x1f\\x7f-\\x9f\\u2028\\u2029\\u202a-\\u202e\\u2066-\\u2069\\u200b-\\u200f\\ufeff\\ud800-\\udfff]+"
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


# Characters XML 1.0 can carry: #x9 #xA #xD, #x20-#xD7FF, #xE000-#xFFFD, #x10000-#x10FFFF.
_XML_UNSAFE = re.compile("[^\\t\\n\\r\\u0020-\\ud7ff\\ue000-\\ufffd\\U00010000-\\U0010ffff]")


def xml_unsafe_count(text: str) -> int:
    """How many characters of ``text`` XML 1.0 cannot represent (controls, lone surrogates, U+FFFE/FFFF)."""
    return len(_XML_UNSAFE.findall(text))


def xml_safe(text: str) -> str:
    """``text`` with every character XML 1.0 cannot represent replaced by U+FFFD (lossy, never silent:
    exporters report the count)."""
    return _XML_UNSAFE.sub("\ufffd", text)


_SURROGATE = re.compile("[\\ud800-\\udfff]")


def has_lone_surrogate(text: str) -> bool:
    """True if ``text`` holds a UTF-16 surrogate code point, which is not valid Unicode text."""
    return _SURROGATE.search(text) is not None
