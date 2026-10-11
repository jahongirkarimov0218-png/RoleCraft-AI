"""docs/RULES.md must describe exactly the rules the registry implements, with the registry's severity and detection."""

import re
from pathlib import Path

from promptgraphify.analyzer import implemented_rules
from promptgraphify.rules import RULES

DOC = (Path(__file__).parent.parent / "docs" / "RULES.md").read_text(encoding="utf-8")
ROWS = {m.group(1): m.groups() for m in re.finditer(r"^\| `([a-z_.]+)` \| (\w+) \| (\w+) / (\w+)", DOC, re.M)}


def test_every_registered_rule_is_documented_and_nothing_else():
    assert set(ROWS) == set(RULES) == implemented_rules()


def test_the_documented_severity_detection_and_certainty_match_the_registry():
    for rule_id, (_, severity, detection, certainty) in ROWS.items():
        rule = RULES[rule_id]
        assert (severity, detection) == (rule.severity, rule.detection), rule_id
        expected = "proven" if rule.certainty in ("proven", "mixed") else "probable"
        assert certainty == expected, rule_id
