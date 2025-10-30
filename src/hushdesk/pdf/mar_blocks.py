from __future__ import annotations

from dataclasses import dataclass
from typing import List


@dataclass
class MarBlock:
    page_index: int
    y_top: float
    y_bottom: float
    lines: List[str]


# Minimal stub: upstream passes each page’s extracted text lines and layout boxes.
_MONTH_KEYWORDS = (
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
)


def find_mar_blocks(pages: List[List[str]]) -> List[MarBlock]:
    blocks: List[MarBlock] = []
    for pidx, lines in enumerate(pages):
        has_schedule = any(
            "Schedule for" in ln and any(month in ln for month in _MONTH_KEYWORDS) for ln in lines
        )
        has_codes = any("Chart Codes" in ln for ln in lines)
        if has_schedule and has_codes:
            blocks.append(MarBlock(page_index=pidx, y_top=0.0, y_bottom=1.0, lines=lines))
    return blocks
