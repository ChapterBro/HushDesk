from __future__ import annotations
import json
import os
from pathlib import Path
from typing import Dict

LIGHT = {
    "bg": "#FFFFFF",
    "surface": "#FFFFFF",
    "text": "#111827",
    "muted": "#6B7280",
    "border": "#E5E7EB",
    "danger": "#C62828",
    "danger_tint": "#FDEAEA",
    "summary_nums": {
        "reviewed": "#111827",
        "hold_miss": "#C62828",
        "held_ok": "#1F2937",
        "compliant": "#374151",
        "dcd": "#4B5563",
    },
    "banner": {"text": "#92400E", "bg": "#FFF7ED", "border": "#FDE68A"},
}

DARK = {
    "bg": "#0B0F14",
    "surface": "#111827",
    "text": "#E5E7EB",
    "muted": "#9CA3AF",
    "border": "#374151",
    "danger": "#EF4444",
    "danger_tint": "#2B1618",
    "summary_nums": {
        "reviewed": "#E5E7EB",
        "hold_miss": "#EF4444",
        "held_ok": "#D1D5DB",
        "compliant": "#C7CBD1",
        "dcd": "#A3A7AE",
    },
    "banner": {"text": "#F59E0B", "bg": "#1F1303", "border": "#4B2E05"},
}


def _windows_pref_dark() -> bool:
    try:
        import winreg  # type: ignore

        personalize = r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, personalize) as key:  # type: ignore[attr-defined]
            value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
            return value == 0
    except Exception:
        return False


def _settings_path() -> Path:
    base = os.environ.get("LOCALAPPDATA") or str(Path.home())
    path = Path(base) / "HushDesk" / "settings.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def load_theme_name() -> str:
    path = _settings_path()
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8")).get("theme", "system")
        except Exception:
            return "system"
    return "system"


def save_theme_name(name: str) -> None:
    path = _settings_path()
    try:
        path.write_text(json.dumps({"theme": name}), encoding="utf-8")
    except Exception:
        pass


def select_palette(name: str) -> Dict[str, str]:
    if name == "light":
        return LIGHT
    if name == "dark":
        return DARK
    return DARK if _windows_pref_dark() else LIGHT
