"""Helpers for room and hall normalization."""
from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import json
import re
from pathlib import Path
from typing import Dict, Iterable, Optional, Tuple

_BASE_PATH = Path(__file__).resolve().parents[1] / "config" / "building_master.json"
_ROOM_RE = re.compile(r"^(?P<num>\d{3})(?:-(?P<bed>[12]))?$")


@dataclass(frozen=True)
class HallRecord:
    name: str
    short: str
    prefix: str
    rooms: Tuple[str, ...]


@lru_cache(maxsize=1)
def _load_master() -> Dict[str, HallRecord]:
    with _BASE_PATH.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    master: Dict[str, HallRecord] = {}
    for name, payload in data.items():
        master[name] = HallRecord(
            name=name,
            short=payload["short"],
            prefix=payload["prefix"],
            rooms=tuple(payload["rooms"]),
        )
    return master


@lru_cache(maxsize=1)
def _room_roster() -> Dict[str, HallRecord]:
    roster: Dict[str, HallRecord] = {}
    for hall in _load_master().values():
        for room in hall.rooms:
            roster[room] = hall
    return roster


def normalize_room(raw: str | None) -> Optional[str]:
    """Normalize raw room text into canonical format.

    The expected format is three digits optionally followed by a bed letter.
    When missing, the bed is assumed to be "-1". Bed letters A/B map to -1/-2.
    Other bed letters are rejected.
    """

    if not raw:
        return None
    cleaned = raw.strip().upper().replace(" ", "")
    if not cleaned:
        return None
    match = _ROOM_RE.match(cleaned)
    if match:
        num = match.group("num")
        bed = match.group("bed") or "1"
        return f"{num}-{bed}"
    if cleaned.endswith("A") or cleaned.endswith("B"):
        core = cleaned[:-1]
        if core.isdigit() and len(core) == 3:
            bed = "1" if cleaned.endswith("A") else "2"
            return f"{core}-{bed}"
    return None


def is_valid_room(room_id: str | None) -> bool:
    if not room_id:
        return False
    return room_id in _room_roster()


def hall_for_room(room_id: str | None) -> Optional[Tuple[str, str]]:
    if not room_id:
        return None
    hall = _room_roster().get(room_id)
    if not hall:
        return None
    return hall.name, hall.short


def prefix_for_room(number: int) -> Optional[str]:
    if number < 100 or number > 999:
        return None
    hundreds = number // 100
    mapping = {1: "100s", 2: "200s", 3: "300s", 4: "400s"}
    return mapping.get(hundreds)


def iter_rooms() -> Iterable[str]:
    return _room_roster().keys()
