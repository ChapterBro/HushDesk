from __future__ import annotations

from hushdesk.core.rules.holds import Rule
from hushdesk.ui.app import _collect_parameter_rules_from_lines, ParameterRuleMatch


def _extract(metrics: list[ParameterRuleMatch]) -> list[tuple[str, str, int]]:
    return [(m.rule.metric, m.rule.op, m.rule.threshold) for m in metrics]


def test_collect_parameter_rules_detects_administer_phrase():
    lines = [
        "Give 1 tablet by mouth every morning.",
        "Administer for SBP < 130 before dosing.",
    ]
    matches = _collect_parameter_rules_from_lines(lines)
    assert _extract(matches) == [("SBP", "<", 130)]
    assert matches[0].snippet.startswith("Administer for SBP < 130")


def test_collect_parameter_rules_merges_wrapped_lines():
    lines = [
        "Hold for SBP less than",
        "110 before administration.",
    ]
    matches = _collect_parameter_rules_from_lines(lines)
    assert _extract(matches) == [("SBP", "<", 110)]
    assert matches[0].snippet == "Hold for SBP less than 110 before administration."


def test_collect_parameter_rules_retains_distinct_occurrences():
    lines = [
        "Give Losartan 50 mg tablet AM.",
        "Hold for SBP less than 110.",
        "Give Losartan 50 mg tablet PM.",
        "Hold for SBP less than 110.",
    ]
    matches = _collect_parameter_rules_from_lines(lines)
    assert _extract(matches) == [("SBP", "<", 110), ("SBP", "<", 110)]
    hints = [m.med_hint for m in matches]
    assert hints[0].startswith("Give Losartan 50 mg tablet AM")
    assert hints[1].startswith("Give Losartan 50 mg tablet PM")


def test_collect_parameter_rules_extracts_room_hint():
    lines = [
        "118A Resident Placeholder",
        "Give 1 tablet by mouth every morning.",
        "Hold for SBP < 120.",
    ]
    matches = _collect_parameter_rules_from_lines(lines)
    assert matches and matches[0].room_hint == "118A"
