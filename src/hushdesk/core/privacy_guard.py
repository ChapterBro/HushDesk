from __future__ import annotations
import re
from typing import Dict, List
from hushdesk.core import building_master as BM

_ALLOWED_WORDS = {
    "date","hall","source","reviewed",
    "hold-miss","held-appropriate","compliant","dc'd",
    "hold","if","sbp","hr","bp","given","code","am","pm"
}
_ROOM_RE  = re.compile(r"^[1-4]\d{2}-(1|2)$")
_TIME_RE  = re.compile(r"^(?:[01]?\d|2[0-3]):[0-5]\d$")
_DATE_RE  = re.compile(r"^\d{2}-\d{2}-\d{4}$")

def sanitize_line(line: str) -> str:
    halls = set(BM.halls())
    chunks = re.findall(r"[A-Za-z0-9:/'\-\(\)]+|[^\sA-Za-z0-9]+", line)
    out: List[str] = []
    for tok in chunks:
        if re.search(r"[A-Za-z]", tok):
            low = tok.lower()
            if (
                low in _ALLOWED_WORDS
                or tok in halls
                or _ROOM_RE.match(tok)
                or _TIME_RE.match(tok)
                or _DATE_RE.match(tok)
                or low == "x"
            ):
                out.append(tok)
            else:
                continue
        else:
            out.append(tok)
    s = "".join(out)
    s = re.sub(r"\s+", " ", s).strip()
    return s

def sanitize_sections_inplace(header: Dict, sections: Dict[str, List[str]]) -> None:
    for k, items in list(sections.items()):
        clean = []
        for line in items:
            sl = sanitize_line(line)
            if sl:
                clean.append(sl)
        sections[k] = clean
    if header.get("hall") not in BM.halls():
        header["hall"] = "UNKNOWN"
