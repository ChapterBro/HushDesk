from __future__ import annotations
import re
from dataclasses import dataclass
from typing import Optional

from hushdesk.core.constants import GIVEN_GLYPHS
from hushdesk.pdf.timeparse import parse_time_token


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


_BP_SPLIT_FIX = re.compile(r"(\d{2,3})\s*/\s*\n\s*(\d{2,3})")
_BP = re.compile(r"\b(\d{2,3})\s*/\s*(\d{2,3})\b")
_HR_LAB = re.compile(r"\b(HR|PULSE)\s*[:\-]?\s*(\d{2,3})\b", re.I)
_INT = re.compile(r"(?<![:/.\d])\b(\d{1,3})\b(?![:/.\d])")


def _join_lines(text: str) -> str:
    return _BP_SPLIT_FIX.sub(r"\1/\2", text or "")


def _extract_time(raw: str) -> Optional[str]:
    if not raw:
        return None

    direct = parse_time_token(raw)
    if direct:
        return direct

    chunks = re.split(r"[\n;,]", raw)
    for chunk in chunks:
        chunk = chunk.strip()
        if not chunk:
            continue
        val = parse_time_token(chunk)
        if not val:
            continue
        low = chunk.lower()
        if ("-" in chunk or "/" in chunk) and ":" not in chunk and "am" not in low and "pm" not in low:
            continue
        return val

    for token in raw.split():
        val = parse_time_token(token)
        if val:
            low = token.lower()
            if ("-" in token or "/" in token) and ":" not in token and "am" not in low and "pm" not in low:
                continue
            return val
    return None


def tokenize_cell_text(cell_text: str, has_hr_track: bool = False) -> Tokens:
    t = Tokens()
    raw = _join_lines(cell_text)
    t.raw = raw

    if any(g in raw for g in GIVEN_GLYPHS):
        t.given = True
    if not t.given and re.search(r"(?:^|\s)[Vv](?:\s|$)", raw):
        t.given = True

    time_val = _extract_time(raw)
    if time_val:
        t.given = True
        t.time = time_val

    if re.search(r"(?:^|\s)[xX](?:\s|$)", raw):
        t.x_mark = True

    if (m := _BP.search(raw)):
        t.sbp = int(m.group(1))
        t.dbp = int(m.group(2))

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
