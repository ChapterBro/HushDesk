from __future__ import annotations
import re
from dataclasses import dataclass
from typing import List, Literal, Match

from hushdesk.core.rules.langmap import normalize_rule_text

Metric = Literal["SBP","HR"]

@dataclass(frozen=True)
class Rule:
    metric: Metric
    op: Literal["<",">"]
    threshold: int

_DISALLOWED = re.compile(r"(?:at or|≤|≥|no less|no more|equal|=)", re.I)
_SBP_LT = re.compile(r"\bSBP\b.*?(?:if\s+)?(?:(?:below|less\s+than)|<)\s*(\d{2,3})", re.I)
_SBP_GT = re.compile(r"\bSBP\b.*?(?:if\s+)?(?:(?:above|greater\s+than)|>)\s*(\d{2,3})", re.I)
_HR_LT  = re.compile(r"\b(HR|Pulse)\b.*?(?:if\s+)?(?:(?:below|less\s+than)|<)\s*(\d{2,3})", re.I)
_HR_GT  = re.compile(r"\b(HR|Pulse)\b.*?(?:if\s+)?(?:(?:above|greater\s+than)|>)\s*(\d{2,3})", re.I)

def _threshold(match: Match[str]) -> int:
    """Return the numeric threshold from any of the regexes."""
    return int(match.group(match.lastindex))

def parse_strict_rules(text: str) -> List[Rule]:
    rules: List[Rule] = []
    for line in text.splitlines():
        line = normalize_rule_text(line)
        if _DISALLOWED.search(line): continue
        if (m := _SBP_LT.search(line)): rules.append(Rule("SBP","<", _threshold(m)))
        if (m := _SBP_GT.search(line)): rules.append(Rule("SBP",">", _threshold(m)))
        if (m := _HR_LT.search(line)):  rules.append(Rule("HR","<",  _threshold(m)))
        if (m := _HR_GT.search(line)):  rules.append(Rule("HR",">",  _threshold(m)))
    seen = set(); uniq: List[Rule] = []
    for r in rules:
        key = (r.metric, r.op, r.threshold)
        if key not in seen: seen.add(key); uniq.append(r)
    return uniq
