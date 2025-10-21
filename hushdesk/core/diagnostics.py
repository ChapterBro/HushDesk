"""Diagnostics helpers for exposing parser metadata."""
from __future__ import annotations

from typing import Dict


def format_meta(meta: Dict[str, object]) -> Dict[str, object]:
    keys = [
        "selected_day",
        "available_columns",
        "file_date_guess",
        "pages_parsed",
        "pages_used",
        "hall_name",
        "hall_short",
        "flags",
    ]
    return {key: meta.get(key) for key in keys}
