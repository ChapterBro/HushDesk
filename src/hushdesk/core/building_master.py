from __future__ import annotations
import json, re, sys, pkgutil
from functools import lru_cache
from importlib.resources import files as ir_files
from pathlib import Path
from typing import Dict, FrozenSet, List

_CANON = re.compile(r"^([1-4]\d{2})-(1|2)$")  # e.g. 201-1

_HALL_ALIASES = {"BRIDGMAN": "BRIDGEMAN"}

def _canon_hall_name(name: str) -> str:
    s = str(name or "").strip().upper()
    return _HALL_ALIASES.get(s, s).title()

def _read_building_master_bytes() -> bytes:
    """
    Resolve hushdesk/config/building_master.json in all contexts:
      • normal package via importlib.resources
      • PyInstaller onefile (_MEIPASS) with collected package data
      • pkgutil.get_data fallback
      • dev-tree fallbacks
    """
    # Preferred: importlib.resources (when PyInstaller collects data for hushdesk)
    try:
        return (ir_files("hushdesk") / "config" / "building_master.json").read_bytes()
    except Exception:
        pass

    # PyInstaller _MEIPASS explicit fallback
    try:
        base = getattr(sys, "_MEIPASS", None)
        if base:
            p = Path(base) / "hushdesk" / "config" / "building_master.json"
            if p.exists():
                return p.read_bytes()
    except Exception:
        pass

    # pkgutil fallback (installed wheel/site‑packages)
    try:
        data = pkgutil.get_data("hushdesk", "config/building_master.json")
        if data:
            return data
    except Exception:
        pass

    # Dev-tree fallbacks
    guesses = [
        Path(__file__).parent.parent / "config" / "building_master.json",         # src layout
        Path.cwd() / "src" / "hushdesk" / "config" / "building_master.json",      # run from repo root
    ]
    for g in guesses:
        if g.exists():
            return g.read_bytes()

    raise FileNotFoundError(
        "building_master.json not bundled. Ensure PyInstaller uses "
        "--collect-data hushdesk and package-data includes config/*.json."
    )

@lru_cache(maxsize=1)
def _payload() -> dict:
    return json.loads(_read_building_master_bytes().decode("utf-8"))

@lru_cache(maxsize=1)
def _room_to_hall() -> Dict[str, str]:
    p = _payload()
    halls = p.get("halls", [])
    m: Dict[str, str] = {}
    for h in halls:
        name = _canon_hall_name(h["name"])
        for r in h["rooms"]:
            if not _CANON.match(r):
                raise ValueError(f"Invalid room id: {r}")
            if r in m:
                raise ValueError(f"Duplicate room id across halls: {r}")
            m[r] = name
    return m

def canonicalize_room(s: str) -> str:
    s = str(s).strip().upper().replace(" ", "")
    if _CANON.match(s):
        return s
    import re as _re
    m = _re.match(r"^([1-4]\d{2})(?:-?([AB]))?$", s)
    if not m:
        raise ValueError(f"Bad room/base: {s!r}")
    base, letter = m.group(1), (m.group(2) or "A")
    suf = _payload()["room_bed_suffix_map"][letter]
    canon = f"{base}{suf}"
    if canon not in _room_to_hall():
        raise ValueError(f"Unknown room: {canon}")
    return canon

def hall_of(room: str) -> str:
    return _room_to_hall()[canonicalize_room(room)]

def is_valid_room(room: str) -> bool:
    try:
        return canonicalize_room(room) in _room_to_hall()
    except Exception:
        return False

def halls() -> List[str]:
    return sorted({h for h in _room_to_hall().values()})

def rooms_in_hall(name: str) -> FrozenSet[str]:
    canon = _canon_hall_name(name)
    return frozenset([r for r, h in _room_to_hall().items() if h == canon])
