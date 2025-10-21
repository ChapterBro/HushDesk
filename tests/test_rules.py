from __future__ import annotations

import pytest

from hushdesk.core import rules


def test_parse_valid_less_than():
    rule = rules.parse_rule("SBP < 110")
    assert rule.metric == "SBP"
    assert rule.operator == "<"
    assert rule.limit == (110,)


def test_parse_valid_greater_than_words():
    rule = rules.parse_rule("Pulse greater than 50")
    assert rule.metric == "HR"
    assert rule.operator == ">"
    assert rule.limit == (50,)


def test_parse_range_exclusive():
    rule = rules.parse_rule("HR 60-90")
    assert rule.operator == "between"
    assert rule.limit == (60, 90)


def test_reject_dbp():
    data = rules.parse_rule("DBP < 80")
    assert isinstance(data, dict)
    assert data["error"] == "dbp_not_supported"


def test_disallowed_inclusive():
    data = rules.parse_rule("SBP less than or equal to 120")
    assert isinstance(data, dict)
    assert data["error"] == "disallowed_operator"


def test_plausibility_bounds():
    data = rules.parse_rule("SBP < 20")
    assert isinstance(data, dict)
    assert data["error"] == "out_of_bounds_threshold"
