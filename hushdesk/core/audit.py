"""Audit engine for BP medication holds."""
from __future__ import annotations

from datetime import datetime
from typing import Dict, List

from .models import DoseResult, Rule
from .parser import ParsedDose, parse_document


def _evaluate_rule(rule: Rule, vitals: Dict[str, int]) -> tuple[bool, bool]:
    """Return (is_in_range, has_data)."""
    metric = rule.metric
    if metric not in vitals:
        return False, False
    value = vitals[metric]
    if rule.operator == "<":
        return value < rule.limit[0], True
    if rule.operator == ">":
        return value > rule.limit[0], True
    lower, upper = rule.limit
    return lower < value < upper, True


def _vitals_map(dose: ParsedDose) -> Dict[str, int]:
    result: Dict[str, int] = {}
    for vital in dose.vitals:
        result[vital.metric] = vital.value
    return result


def evaluate_dose(dose: ParsedDose) -> DoseResult:
    vitals = _vitals_map(dose)
    flags = list(dose.flags)
    if dose.rule_error == "disallowed_operator":
        return DoseResult(
            room=dose.room,
            time_local=dose.time_local,
            rule=None,
            vitals=tuple(dose.vitals),
            admin=dose.admin,
            decision="EXCEPTION",
            reason="disallowed_operator",
            med_name=dose.med_name,
        )
    if dose.rule is None:
        return DoseResult(
            room=dose.room,
            time_local=dose.time_local,
            rule=None,
            vitals=tuple(dose.vitals),
            admin=dose.admin,
            decision="EXCEPTION",
            reason=dose.rule_error or "ambiguous_rule",
            med_name=dose.med_name,
        )
    in_range, has_data = _evaluate_rule(dose.rule, vitals)
    if not has_data:
        reason = "vitals_stale" if "vitals_stale" in flags else "missing_vitals"
        return DoseResult(
            room=dose.room,
            time_local=dose.time_local,
            rule=dose.rule,
            vitals=tuple(dose.vitals),
            admin=dose.admin,
            decision="EXCEPTION",
            reason=reason,
            med_name=dose.med_name,
        )
    if "vitals_stale" in flags:
        return DoseResult(
            room=dose.room,
            time_local=dose.time_local,
            rule=dose.rule,
            vitals=tuple(dose.vitals),
            admin=dose.admin,
            decision="EXCEPTION",
            reason="vitals_stale",
            med_name=dose.med_name,
        )
    if not in_range and dose.admin == "NOT_GIVEN_HELD":
        return DoseResult(
            room=dose.room,
            time_local=dose.time_local,
            rule=dose.rule,
            vitals=tuple(dose.vitals),
            admin=dose.admin,
            decision="HELD",
            reason="held_out_of_range",
            med_name=dose.med_name,
        )
    if in_range:
        return DoseResult(
            room=dose.room,
            time_local=dose.time_local,
            rule=dose.rule,
            vitals=tuple(dose.vitals),
            admin=dose.admin,
            decision="COMPLIANT",
            reason=None,
            med_name=dose.med_name,
        )
    return DoseResult(
        room=dose.room,
        time_local=dose.time_local,
        rule=dose.rule,
        vitals=tuple(dose.vitals),
        admin=dose.admin,
        decision="EXCEPTION",
        reason="rule_violation_given" if dose.admin == "GIVEN" else "missing_vitals",
        med_name=dose.med_name,
    )


def run_audit(path: str, audit_date: datetime) -> tuple[List[DoseResult], Dict[str, object]]:
    parse_result = parse_document(path, audit_date)
    evaluated = [evaluate_dose(dose) for dose in parse_result.doses]
    reviewed = len(evaluated)
    held = sum(1 for item in evaluated if item.decision == "HELD")
    compliant = sum(1 for item in evaluated if item.decision == "COMPLIANT")
    exceptions = sum(1 for item in evaluated if item.decision == "EXCEPTION")
    invariant_ok = reviewed == held + compliant + exceptions
    summary = {
        "reviewed": reviewed,
        "held": held,
        "compliant": compliant,
        "exceptions": exceptions,
        "invariant_ok": invariant_ok,
    }
    meta = dict(parse_result.meta)
    meta["summary"] = summary
    return evaluated, meta
