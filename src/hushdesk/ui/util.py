from __future__ import annotations
import datetime as dt
import re
from typing import Dict, List, Tuple, Optional
from zoneinfo import ZoneInfo

from hushdesk.core import building_master as BM
from hushdesk.core.engine.decide import DecisionRecord

CENTRAL_TZ = ZoneInfo("America/Chicago")
TRACK_ORDER = {"AM": 0, "PM": 1}


def chicago_now_str() -> str:
    return dt.datetime.now(tz=CENTRAL_TZ).strftime("%m-%d-%Y %H:%M")


def hall_from_rooms(rooms: List[str]) -> Tuple[Optional[str], Optional[int]]:
    counts: Dict[str, int] = {}
    for room in rooms:
        try:
            canon = BM.canonicalize_room(room)
            hall = BM.hall_of(canon)
            counts[hall] = counts.get(hall, 0) + 1
        except Exception:
            continue
    if not counts:
        return None, None
    hall = max(counts.items(), key=lambda kv: kv[1])[0]
    sample = next(iter(BM.rooms_in_hall(hall)))
    hall_num = int(sample[0]) * 100
    return hall, hall_num


def _room_base(room: str) -> int:
    m = re.match(r"(\d{3})", room)
    return int(m.group(1)) if m else 999


def sort_room_track(item: Tuple[str, str]) -> Tuple[int, str, int]:
    room, track = item
    return (_room_base(room), room, TRACK_ORDER.get(track, 99))


def summarize_counts(records: List[DecisionRecord]) -> Dict[str, int]:
    summary = {"reviewed": 0, "hold_miss": 0, "held_ok": 0, "compliant": 0, "dcd": 0}
    seen_doses = set()
    for record in records:
        dose_key = (record.room, record.time_track, record.date, record.source.get("page"), record.source.get("col"))
        if dose_key not in seen_doses:
            seen_doses.add(dose_key)
            summary["reviewed"] += 1
        if record.decision == "HOLD-MISS":
            summary["hold_miss"] += 1
        elif record.decision == "HELD-APPROPRIATE":
            summary["held_ok"] += 1
        elif record.decision == "COMPLIANT":
            summary["compliant"] += 1
        elif record.decision == "DC'D":
            summary["dcd"] += 1
    return summary
