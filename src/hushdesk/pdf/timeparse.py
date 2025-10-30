from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

_AMPM = r"(?:\b(?:am|pm)\b)"
_TIME_HHMM = r"\b([01]?\d|2[0-3])[:]?([0-5]\d)\b"
_TIME_HH = r"\b([1-9]|1[0-2])\s*(" + _AMPM + r")\b"
_RANGE = r"\b(\d{1,2})(?:[:.]?(\d{2}))?\s*([ap]m)?\s*-\s*(\d{1,2})(?:[:.]?(\d{2}))?\s*([ap]m)?\b"
_BLOCKS = {
    # common grid headers found on MARs
    "6a-10": ("06:00", "10:00", "am"),
    "11a -": ("11:00", "13:59", "noon"),
    "12p-2": ("12:00", "14:00", "noon"),
    "4pm-7": ("16:00", "19:00", "pm"),
    "8pm-1": ("20:00", "01:00", "overnight"),
    "HS": (None, None, "hs"),
    "AM": (None, None, "am"),
    "PM": (None, None, "pm"),
}


@dataclass(frozen=True)
class TimeNorm:
    raw_time: str
    normalized_time: Optional[str]  # "HH:MM"
    time_range: Optional[str]  # "HH:MM-HH:MM"
    slot: Optional[str]  # "am|noon|pm|evening|hs|overnight"


def _pad(h: int, m: int) -> str:
    return f"{h:02d}:{m:02d}"


def _to_24h(h: int, ampm: Optional[str]) -> int:
    if ampm is None:
        return h
    ampm = ampm.lower()
    if ampm == "am":
        return 0 if h == 12 else h
    if ampm == "pm":
        return 12 if h == 12 else h + 12
    return h


def _normalize_range_hours(
    sh: int, sm: int, sap: Optional[str], eh: int, em: int, eap: Optional[str]
) -> tuple[int, int, int, int]:
    start_hour = _to_24h(sh, sap)
    end_hour = _to_24h(eh, eap)

    if eap is None and sap in {"am", "pm"}:
        end_hour = eh
        if sap == "pm":
            if eh >= sh:
                end_hour = eh + 12
            elif eh <= 5:
                end_hour = eh
            else:
                end_hour = eh + 12
        else:  # start in AM
            if eh < sh:
                end_hour = eh + 12
    elif eap is None:
        end_hour = eh

    start_hour %= 24
    end_hour %= 24
    return start_hour, sm, end_hour, em


def normalize_time_token(s: str) -> TimeNorm:
    raw = (s or "").strip()
    key = raw.replace(" ", "").lower()
    # Known block headers
    for block, (start, end, slot) in _BLOCKS.items():
        if key.startswith(block.replace(" ", "").lower()):
            return TimeNorm(
                raw_time=raw,
                normalized_time=None,
                time_range=f"{start}-{end}" if start and end else None,
                slot=slot,
            )

    # HHMM or H:MM 24h
    m = re.search(_TIME_HHMM, raw)
    if m and len(m.groups()) == 2:
        h = int(m.group(1))
        mm = int(m.group(2))
        return TimeNorm(raw, _pad(h, mm), None, None)

    # 12h like "8 pm"
    m = re.search(_TIME_HH, raw, flags=re.IGNORECASE)
    if m:
        h = int(m.group(1))
        ampm = m.group(2).lower().replace(".", "")
        slot = "pm" if ampm == "pm" else "am"
        return TimeNorm(raw, _pad(_to_24h(h, ampm), 0), None, slot)

    # Ranges like "4pm-7" or "6:30-10"
    m = re.search(_RANGE, raw, flags=re.IGNORECASE)
    if m:
        sh = int(m.group(1))
        sm = int(m.group(2) or 0)
        sap_raw = (m.group(3) or "").lower().replace(".", "")
        sap = None
        if sap_raw in {"am", "pm"}:
            sap = sap_raw
        eh = int(m.group(4))
        em = int(m.group(5) or 0)
        eap_raw = (m.group(6) or "").lower().replace(".", "")
        eap = None
        if eap_raw in {"am", "pm"}:
            eap = eap_raw
        start_hour, start_min, end_hour, end_min = _normalize_range_hours(sh, sm, sap, eh, em, eap)
        return TimeNorm(raw, None, f"{_pad(start_hour, start_min)}-{_pad(end_hour, end_min)}", None)

    # Fallback: unknown token → slot guess
    lower = raw.lower()
    for guess in ("am", "noon", "pm", "evening", "hs", "overnight"):
        if guess in lower:
            return TimeNorm(raw, None, None, guess)
    return TimeNorm(raw, None, None, None)


def parse_time_token(s: str) -> Optional[str]:
    """
    Backwards-compatible wrapper returning the normalized clock time, if present.
    """
    norm = normalize_time_token(s)
    return norm.normalized_time
