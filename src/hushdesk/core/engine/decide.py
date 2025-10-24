from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, List, Literal, Dict
from hushdesk.core.rules.holds import Rule
from hushdesk.core.constants import ALLOWED_HELD_CODES

Decision = Literal["HOLD-MISS","HELD-APPROPRIATE","COMPLIANT","DC'D"]

@dataclass
class CellTokens:
    given: bool = False
    time: Optional[str] = None
    chart_code: Optional[int] = None
    x_mark: bool = False
    sbp: Optional[int] = None
    dbp: Optional[int] = None
    hr: Optional[int] = None

@dataclass
class DecisionRecord:
    room: str
    hall: str
    date: str
    time_track: Literal["AM","PM"]
    reviewed: bool
    decision: Decision
    rule: Optional[Dict]
    measured: Dict
    admin: Dict
    notes: str
    source: Dict

def _triggers(rule: Rule, sbp: Optional[int], hr: Optional[int]) -> bool:
    if rule.metric == "SBP" and sbp is not None:
        return (rule.op == "<" and sbp < rule.threshold) or (rule.op == ">" and sbp > rule.threshold)
    if rule.metric == "HR" and hr is not None:
        return (rule.op == "<" and hr < rule.threshold) or (rule.op == ">" and hr > rule.threshold)
    return False

def decide_due(*, room: str, hall: str, date: str, track: Literal["AM","PM"],
               rules: List[Rule], tokens_due: CellTokens, tokens_bp: Optional[CellTokens],
               source: Dict) -> List[DecisionRecord]:
    out: List[DecisionRecord] = []
    reviewed = True

    if tokens_due.x_mark:
        out.append(DecisionRecord(
            room, hall, date, track, reviewed, "DC'D", None,
            measured={"sbp": tokens_bp.sbp if tokens_bp else tokens_due.sbp,
                      "dbp": tokens_bp.dbp if tokens_bp else tokens_due.dbp,
                      "hr":  tokens_bp.hr  if tokens_bp  else tokens_due.hr},
            admin={"given": False, "time": None, "chart_code": None, "x_mark": True},
            notes="X in due cell",
            source=source,
        ))
        return out

    if tokens_due.chart_code is not None:
        code = tokens_due.chart_code
        if code in ALLOWED_HELD_CODES:
            out.append(DecisionRecord(
                room, hall, date, track, reviewed, "HELD-APPROPRIATE", None,
                measured={"sbp": tokens_bp.sbp if tokens_bp else tokens_due.sbp,
                          "dbp": tokens_bp.dbp if tokens_bp else tokens_due.dbp,
                          "hr":  tokens_bp.hr  if tokens_bp  else tokens_due.hr},
                admin={"given": False, "time": None, "chart_code": code, "x_mark": False},
                notes=f"code {code}",
                source=source,
            ))
            return out
        else:
            return out

    if tokens_due.given:
        sbp = tokens_bp.sbp if (tokens_bp and tokens_bp.sbp is not None) else tokens_due.sbp
        hr  = tokens_bp.hr  if (tokens_bp and tokens_bp.hr  is not None) else tokens_due.hr
        hold_emitted = False
        for r in rules:
            if _triggers(r, sbp, hr):
                hold_emitted = True
                out.append(DecisionRecord(
                    room, hall, date, track, reviewed, "HOLD-MISS",
                    {"type": r.metric, "op": r.op, "threshold": r.threshold},
                    measured={"sbp": sbp, "dbp": tokens_bp.dbp if tokens_bp else tokens_due.dbp, "hr": hr},
                    admin={"given": True, "time": tokens_due.time, "chart_code": None, "x_mark": False},
                    notes=f"Hold if {r.metric} {r.op} {r.threshold}; " +
                          (f"BP {sbp}/{tokens_bp.dbp if tokens_bp else tokens_due.dbp}" if r.metric=="SBP" else f"HR {hr}") +
                          (f"; given {tokens_due.time}" if tokens_due.time else "; given"),
                    source=source,
                ))
        if not hold_emitted:
            phr = None
            for r in rules:
                if r.metric == "SBP":
                    phr = f"Hold if SBP {r.op} {r.threshold}"; break
            if not phr and rules:
                r = rules[0]; phr = f"Hold if {r.metric} {r.op} {r.threshold}"
            note_v = (f"BP {sbp}/{tokens_bp.dbp if tokens_bp else tokens_due.dbp}" if sbp is not None
                      else f"HR {hr}" if hr is not None else "")
            out.append(DecisionRecord(
                room, hall, date, track, reviewed, "COMPLIANT", None,
                measured={"sbp": sbp, "dbp": tokens_bp.dbp if tokens_bp else tokens_due.dbp, "hr": hr},
                admin={"given": True, "time": tokens_due.time, "chart_code": None, "x_mark": False},
                notes=f"{phr}; {note_v}; " + (f"given {tokens_due.time}" if tokens_due.time else "given"),
                source=source,
            ))
        return out

    return out
