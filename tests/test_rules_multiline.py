from __future__ import annotations

from hushdesk.ui import app  # noqa: F401  ensure rule patching side-effect
from hushdesk.core.rules.holds import parse_strict_rules


def test_parse_rules_handles_multiline_thresholds():
    text = "Hold for SBP less\nthan 90 and HR less than 60"
    rules = parse_strict_rules(text)
    payload = {(rule.metric, rule.op, rule.threshold) for rule in rules}
    assert ("SBP", "<", 90) in payload
    assert ("HR", "<", 60) in payload
