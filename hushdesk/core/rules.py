"""Medication rule parsing compliant with the BP hold canon."""
from __future__ import annotations

import re
from typing import Dict, Optional

from .models import Rule

_ALLOWED_METRICS: Dict[str, str] = {
    "sbp": "SBP",
    "systolic": "SBP",
    "systolic bp": "SBP",
    "hr": "HR",
    "pulse": "HR",
    "heart rate": "HR",
}

_DISALLOWED_KEYWORDS = {
    "=",
    "equal",
    "inclusive",
    "no less",
    "no more",
    "at or below",
    "at or above",
    "less than or",
    "greater than or",
    "no greater",
    "no smaller",
    "<=",
    ">=",
    "[",
    "]",
}

_RANGE_SEP = re.compile(r"\s*[–-]\s*")
_NUMBER = re.compile(r"(?<!\d)(\d{2,3})(?!\d)")
_BETWEEN = re.compile(r"\bbetween\s+(\d{2,3})\s+and\s+(\d{2,3})\b")
_OPERATOR_WORDS = {
    "less than": "<",
    "below": "<",
    "under": "<",
    "greater than": ">",
    "above": ">",
    "over": ">",
}


class RuleParseError(RuntimeError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _metric_from_text(text: str) -> Optional[str]:
    lowered = text.lower()
    for key, metric in _ALLOWED_METRICS.items():
        if key in lowered:
            return metric
    if "dbp" in lowered or "diastolic" in lowered:
        raise RuleParseError("dbp_not_supported")
    return None


def _extract_operator(text: str) -> Optional[str]:
    if "<" in text:
        return "<"
    if ">" in text:
        return ">"
    match = _BETWEEN.search(text.lower())
    if match:
        return "between"
    for phrase, operator in _OPERATOR_WORDS.items():
        if phrase in text.lower():
            return operator
    if _RANGE_SEP.search(text):
        return "between"
    return None


def _check_disallowed(text: str) -> None:
    lowered = text.lower()
    for bad in _DISALLOWED_KEYWORDS:
        if bad in lowered:
            raise RuleParseError("disallowed_operator")


def _parse_numbers(text: str) -> list[int]:
    return [int(match.group(1)) for match in _NUMBER.finditer(text)]


_PLAUSIBILITY = {
    "SBP": (50, 250),
    "HR": (30, 180),
}


def _check_plausibility(metric: str, values: list[int]) -> None:
    lower, upper = _PLAUSIBILITY[metric]
    for value in values:
        if value < lower or value > upper:
            raise RuleParseError("out_of_bounds_threshold")


def parse_rule(text: str | None) -> Rule | Dict[str, str]:
    """Parse a rule description into a :class:`Rule` or error mapping."""

    if not text or not text.strip():
        return {"error": "empty"}
    original = text.strip()
    try:
        metric = _metric_from_text(original)
        if not metric:
            return {"error": "unsupported_metric"}
        _check_disallowed(original)
        operator = _extract_operator(original)
        if not operator:
            return {"error": "operator_not_found"}
        numbers = _parse_numbers(original)
        if operator == "between":
            if len(numbers) >= 2:
                lower, upper = sorted(numbers[:2])
            else:
                parts = _RANGE_SEP.split(original)
                if len(parts) != 2:
                    raise RuleParseError("missing_bounds")
                numbers = _parse_numbers(" ".join(parts))
                if len(numbers) != 2:
                    raise RuleParseError("missing_bounds")
                lower, upper = sorted(numbers)
            if lower == upper:
                raise RuleParseError("non_exclusive_range")
            _check_plausibility(metric, [lower, upper])
            return Rule(metric=metric, operator="between", limit=(lower, upper), text=original)
        if not numbers:
            raise RuleParseError("missing_bounds")
        threshold = numbers[0]
        _check_plausibility(metric, [threshold])
        return Rule(metric=metric, operator=operator, limit=(threshold,), text=original)
    except RuleParseError as exc:
        return {"error": exc.code}
