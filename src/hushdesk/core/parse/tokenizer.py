from __future__ import annotations
import re
from dataclasses import dataclass
from typing import Optional

from hushdesk.core.constants import GIVEN_GLYPHS

@dataclass
class Tokens:
    given: bool = False
    time: Optional[str] = None
    chart_code: Optional[int] = None
    x_mark: bool = False
    sbp: Optional[int] = None
    dbp: Optional[int] = None
    hr: Optional[int] = None
    raw: str = ""

_TIME = re.compile(r"\b([01]?\d|2[0-3]):[0-5]\d\b")
_BP_SPLIT_FIX = re.compile(r"(\d{2,3})\s*/\s*\n\s*(\d{2,3})")
_BP = re.compile(r"\b(\d{2,3})\s*/\s*(\d{2,3})\b")
_HR_LAB = re.compile(r"\b(HR|PULSE)\s*[:\-]?\s*(\d{2,3})\b", re.I)
_INT = re.compile(r"(?<![:/.\d])\b(\d{1,3})\b(?![:/.\d])")

def _join_lines(text: str) -> str:
    return _BP_SPLIT_FIX.sub(r"\1/\2", text or "")

def tokenize_cell_text(cell_text: str, has_hr_track: bool = False) -> Tokens:
    t = Tokens()
    raw = _join_lines(cell_text)
    t.raw = raw

    # Given markers: common glyphs and isolated ASCII V
    if any(g in raw for g in GIVEN_GLYPHS):
        t.given = True
    if not t.given and re.search(r"(?:^|\s)[Vv](?:\s|$)", raw):
        t.given = True
    if (m := _TIME.search(raw)):
        t.given = True
        t.time = m.group(0)

    if re.search(r"(?:^|\s)[xX](?:\s|$)", raw):
        t.x_mark = True

    if (m := _BP.search(raw)):
        t.sbp = int(m.group(1)); t.dbp = int(m.group(2))

    if (m := _HR_LAB.search(raw)):
        t.hr = int(m.group(2))
    elif has_hr_track:
        ints = [int(x) for x in _INT.findall(raw)]
        if ints and 40 <= ints[-1] <= 180:
            t.hr = ints[-1]

    ints = [int(x) for x in _INT.findall(raw)]
    if ints:
        code = ints[-1]
        if not (t.hr == code or (t.sbp == code or t.dbp == code)):
            t.chart_code = code

    return t
