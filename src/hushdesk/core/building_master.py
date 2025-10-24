from __future__ import annotations
import json, re
from functools import lru_cache
from importlib.resources import files
from typing import Dict, FrozenSet, List

_CANON = re.compile(r"^([1-4]\d{2})-(1|2)$")  # e.g., 201-1
_HALL_ALIASES = {"BRIDGMAN": "Bridgeman"}

@lru_cache(maxsize=1)
def normalize_hall(name: str) -> str:
    if not name:
        raise ValueError("Empty hall name")
    n = str(name).strip()
    k = n.upper()
    return _HALL_ALIASES.get(k, n)


def _payload() -> dict:
    data = files("hushdesk").joinpath("config/building_master.json").read_bytes()
    return json.loads(data.decode("utf-8"))

@lru_cache(maxsize=1)
def _room_to_hall() -> Dict[str, str]:
    p = _payload()
    halls = p.get("halls", [])
    m: Dict[str, str] = {}
    for h in halls:
        name = h["name"]
        for r in h["rooms"]:
            if not _CANON.match(r): raise ValueError(f"Invalid room id: {r}")
            if r in m: raise ValueError(f"Duplicate room id across halls: {r}")
            m[r] = name
    return m

def canonicalize_room(s: str) -> str:
    s = str(s).strip().upper().replace(" ", "")
    if _CANON.match(s): return s
    m = re.match(r"^([1-4]\d{2})(?:-?([AB]))?$", s)
    if not m: raise ValueError(f"Bad room/base: {s!r}")
    base, letter = m.group(1), (m.group(2) or "A")
    suf = _payload()["room_bed_suffix_map"][letter]
    canon = f"{base}{suf}"
    if canon not in _room_to_hall(): raise ValueError(f"Unknown room: {canon}")
    return canon

def hall_of(room: str) -> str: return _room_to_hall()[canonicalize_room(room)]
def is_valid_room(room: str) -> bool:
    try: return canonicalize_room(room) in _room_to_hall()
    except Exception: return False
def halls() -> List[str]: return sorted({h for h in _room_to_hall().values()})
def rooms_in_hall(name: str) -> FrozenSet[str]:
    return frozenset([r for r, h in _room_to_hall().items() if h == name])
