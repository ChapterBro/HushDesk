from __future__ import annotations

import statistics
from collections import defaultdict
from typing import Iterable, List, Sequence

from .engine_base import Cell, Row, Word

__all__ = ["Row", "Cell", "extract_rows"]

_HEADER_SIGNATURE = {"room", "medication", "am", "pm"}


def extract_rows(words: Iterable[Word]) -> List[Row]:
    word_list = [w for w in words if w.text.strip()]
    if not word_list:
        return []

    heights = [w.height for w in word_list if w.height > 0]
    median_height = statistics.median(heights) if heights else 10.0
    y_tol = max(median_height * 0.6, 1.0)

    buckets: dict[tuple[int, int], List[Word]] = defaultdict(list)
    for w in word_list:
        bucket = int(round(w.y0 / y_tol))
        buckets[(w.page, bucket)].append(w)

    rows: List[Row] = []
    for page_bucket in sorted(buckets, key=lambda b: (b[0], b[1])):
        page, _ = page_bucket
        row_words = sorted(buckets[page_bucket], key=lambda w: (w.x0, w.y0))
        cells = _words_to_cells(row_words, median_height)
        if len(cells) < 1:
            continue
        y0 = min(w.y0 for w in row_words)
        y1 = max(w.y1 for w in row_words)
        row = Row(cells=cells, y0=y0, y1=y1, page=page)
        rows.append(row)

    filtered: List[Row] = []
    for row in rows:
        if len(row.cells) < 4:
            continue
        if _is_header(row):
            continue
        filtered.append(row)
    return filtered


def _words_to_cells(row_words: Sequence[Word], median_height: float) -> List[Cell]:
    if not row_words:
        return []
    cells: List[Cell] = []
    current: List[Word] = [row_words[0]]
    gap_ceiling = max(median_height * 1.2, 2.0)
    for word in row_words[1:]:
        prev = current[-1]
        gap = word.x0 - prev.x1
        if gap > gap_ceiling:
            cells.append(_merge_words(current))
            current = [word]
        else:
            current.append(word)
    cells.append(_merge_words(current))
    return cells


def _merge_words(words: Sequence[Word]) -> Cell:
    raw = " ".join(w.text for w in words).strip()
    text = _normalize_cell_text(raw)
    x0 = min(w.x0 for w in words)
    y0 = min(w.y0 for w in words)
    x1 = max(w.x1 for w in words)
    y1 = max(w.y1 for w in words)
    return Cell(text=text, x0=x0, y0=y0, x1=x1, y1=y1)


def _is_header(row: Row) -> bool:
    normalized = [cell.text.strip().lower() for cell in row.cells if cell.text.strip()]
    if not normalized:
        return False
    return set(normalized) >= _HEADER_SIGNATURE


def _normalize_cell_text(raw: str) -> str:
    if not raw:
        return ""
    stripped = raw.strip()
    middle_dot = "\u00b7"
    if stripped == middle_dot:
        return "—"
    if middle_dot in raw:
        if any(ch.isdigit() for ch in stripped):
            return raw.replace(middle_dot, "✓")
        return raw.replace(middle_dot, "—")
    return raw
