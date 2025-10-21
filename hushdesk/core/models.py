"""Shared dataclasses used across the application."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Optional, Tuple


Metric = Literal["SBP", "HR"]
Operator = Literal["<", ">", "between"]
AdminState = Literal["GIVEN", "NOT_GIVEN_HELD", "UNKNOWN"]
Decision = Literal["COMPLIANT", "HELD", "EXCEPTION"]


@dataclass(frozen=True)
class Rule:
    metric: Metric
    operator: Operator
    limit: Tuple[int, ...]
    text: str

    def bounds(self) -> Tuple[int, int]:
        if self.operator == "between":
            return self.limit[0], self.limit[1]
        if self.operator == "<":
            return float("-inf"), self.limit[0]
        return self.limit[0], float("inf")


@dataclass
class Vital:
    metric: Metric
    value: int
    taken_at: datetime


@dataclass
class DoseResult:
    room: str
    time_local: datetime
    rule: Rule | None
    vitals: Tuple[Vital, ...]
    admin: AdminState
    decision: Decision
    reason: Optional[str]
    med_name: Optional[str] = None
