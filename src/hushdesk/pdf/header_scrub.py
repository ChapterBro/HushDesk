import re
from typing import Iterable, List

# Patterns that may expose PII in MAR headers/footers; we DROP these lines entirely.
_PATTERNS = [
    r"\bDOB\b",
    r"\bAdmit Date\b",
    r"\bRoom\b",
    r"\bResident\b",
    r"\bPrinted on\b",
    r"\bPage:\s*\d+\s*of\s*\d+\b",
    r"\(\d{3,}\)",  # MRN-like or resident id in parens
    r"[A-Z]{2,},\s+[A-Z][a-z]+",  # LAST, First
]


def scrub_header(lines: Iterable[str]) -> List[str]:
    out: List[str] = []
    for ln in lines:
        keep = True
        for pattern in _PATTERNS:
            if re.search(pattern, ln):
                keep = False
                break
        if keep:
            out.append(ln)
    return out

