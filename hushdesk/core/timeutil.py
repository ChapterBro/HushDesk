"""Time helpers anchored to the America/Chicago timezone."""
from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Iterable, Optional

from zoneinfo import ZoneInfo

CT = ZoneInfo("America/Chicago")


def now_ct() -> datetime:
    return datetime.now(tz=CT)


def default_audit_day(reference: Optional[datetime] = None) -> date:
    ref = reference or now_ct()
    ct_ref = ref.astimezone(CT)
    return (ct_ref - timedelta(days=1)).date()


def combine_ct(day: date, when: time) -> datetime:
    return datetime.combine(day, when, tzinfo=CT)


def parse_time_token(token: str) -> Optional[time]:
    token = token.strip()
    if not token:
        return None
    if token.isdigit() and len(token) in {3, 4}:
        padded = token.zfill(4)
        hour = int(padded[:2])
        minute = int(padded[2:])
    else:
        parts = token.split(":")
        if len(parts) != 2:
            return None
        hour = int(parts[0])
        minute = int(parts[1])
    if hour > 23 or minute > 59:
        return None
    return time(hour=hour, minute=minute)


def closest_vital(target: datetime, vitals: Iterable[datetime], window: timedelta) -> Optional[datetime]:
    best = None
    best_delta = timedelta.max
    for stamp in vitals:
        delta = abs(stamp - target)
        if delta <= window and delta < best_delta:
            best = stamp
            best_delta = delta
    return best
