from __future__ import annotations

from collections import defaultdict
from typing import Iterable, List, Sequence

from .engine_base import Cell, Row, Word
from .grid_geometry import extract_grid_rows

__all__ = ["Row", "Cell", "extract_rows"]

_HEADER_SIGNATURE = {"room", "medication", "am", "pm"}
_DAY_NAMES = {"SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"}


def extract_rows(words: Iterable[Word], *, source_path: str | None = None) -> List[Row]:
    word_list = [w for w in words if w.text.strip()]
    if not word_list:
        return []

    rows: List[Row] = []
    if source_path:
        page_words: dict[int, List[Word]] = defaultdict(list)
        for word in word_list:
            page_words[word.page].append(word)
        grid_rows = extract_grid_rows(source_path, page_words)
        covered_pages = set(grid_rows.keys())
        for page_index in sorted(covered_pages):
            rows.extend(grid_rows[page_index])
        remaining_words = [w for w in word_list if w.page not in covered_pages]
        if remaining_words:
            rows.extend(_legacy_extract_rows(remaining_words))
    else:
        rows = _legacy_extract_rows(word_list)

    rows.sort(key=lambda r: (r.page, r.y0, r.y1))
    return _filter_rows(rows)


def _legacy_extract_rows(words: Sequence[Word]) -> List[Row]:
    if not words:
        return []

    heights = [w.height for w in words if w.height > 0]
    median_height = sorted(heights)[len(heights) // 2] if heights else 10.0
    y_tol = max(median_height * 0.6, 1.0)

    buckets: dict[tuple[int, int], List[Word]] = defaultdict(list)
    for w in words:
        bucket = int(round(w.y0 / y_tol))
        buckets[(w.page, bucket)].append(w)

    rows: List[Row] = []
    for page_bucket in sorted(buckets, key=lambda b: (b[0], b[1])):
        page, _ = page_bucket
        row_words = sorted(buckets[page_bucket], key=lambda w: (w.x0, w.y0))
        cells = _words_to_cells(row_words, median_height)
        if not cells:
            continue
        y0 = min(w.y0 for w in row_words)
        y1 = max(w.y1 for w in row_words)
        rows.append(Row(cells=cells, y0=y0, y1=y1, page=page))
    return rows


def _filter_rows(rows: Sequence[Row]) -> List[Row]:
    filtered: List[Row] = []
    for row in rows:
        if len(row.cells) < 4:
            continue
        if _is_header(row):
            continue
        if _looks_like_day_header(row):
            continue
        leading = [cell.text.strip() for cell in row.cells[:2]]
        if not any(leading):
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
    if set(normalized) >= _HEADER_SIGNATURE:
        return True
    return any(token in {"room", "resident"} for token in normalized[:2])


def _looks_like_day_header(row: Row) -> bool:
    tokens = [cell.text.strip().upper() for cell in row.cells if cell.text.strip()]
    if not tokens:
        return False
    day_tokens = sum(1 for token in tokens if token in _DAY_NAMES or token.rstrip("1234567890") in _DAY_NAMES)
    number_tokens = sum(1 for token in tokens if token.isdigit() and 1 <= int(token) <= 31)
    if day_tokens >= max(3, len(tokens) // 2):
        return True
    if number_tokens >= max(5, len(tokens) // 2):
        return True
    lead = [cell.text.strip().upper() for cell in row.cells[:2] if cell.text.strip()]
    if lead and all(entry.isdigit() for entry in lead):
        return True
    return False


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
