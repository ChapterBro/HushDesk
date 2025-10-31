from __future__ import annotations

import json
import os
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from ._mupdf import import_fitz
from .engine_base import Cell, Row, Word

fitz = import_fitz(optional=True)  # type: ignore[assignment]

GridBand = Tuple[float, float]
Segments = List[Tuple[float, float, float, float]]

_DEBUG_ENV = "HUSHDESK_MAR_DEBUG_DIR"


@dataclass
class PageGeometry:
    page_index: int
    row_edges: List[float]
    col_edges: List[float]


def extract_grid_rows(
    pdf_path: str,
    words_by_page: Dict[int, List[Word]],
) -> Dict[int, List[Row]]:
    """
    Build table rows by leveraging vector line segments from MuPDF.
    Falls back to an empty dict when MuPDF is unavailable or the grid
    lines are not detected so the caller can use legacy heuristics.
    """
    if fitz is None:
        return {}

    doc = fitz.open(pdf_path)
    try:
        debug_dir = _debug_dir()
        rows_by_page: Dict[int, List[Row]] = {}
        for page_index, words in words_by_page.items():
            if not words:
                continue
            page = doc.load_page(page_index)
            geometry = _derive_page_geometry(page, words)
            if geometry is None:
                continue
            rows = _rows_from_geometry(page_index, geometry, words)
            if not rows:
                continue
            rows_by_page[page_index] = rows
            if debug_dir:
                _dump_debug(debug_dir, pdf_path, page_index, geometry, rows)
        return rows_by_page
    finally:
        doc.close()


def _debug_dir() -> Optional[Path]:
    raw = os.getenv(_DEBUG_ENV)
    if not raw:
        return None
    try:
        path = Path(raw).expanduser()
        path.mkdir(parents=True, exist_ok=True)
        return path
    except Exception:
        return None


def _derive_page_geometry(page, words: Sequence[Word]) -> Optional[PageGeometry]:
    segments = _collect_segments(page)
    if not segments:
        return None

    rect = page.rect
    width = float(rect.width or 612.0)
    height = float(rect.height or 792.0)
    min_h_len = max(48.0, width * 0.35)
    min_v_len = max(48.0, height * 0.20)

    horizontals: List[float] = []
    verticals: List[float] = []

    for x0, y0, x1, y1 in segments:
        dx = abs(x1 - x0)
        dy = abs(y1 - y0)
        if dy <= 1.2 and dx >= min_h_len:
            horizontals.append((y0 + y1) / 2.0)
        elif dx <= 1.2 and dy >= min_v_len:
            verticals.append((x0 + x1) / 2.0)

    horizontals = _cluster_positions(horizontals, tol=1.4)
    verticals = _cluster_positions(verticals, tol=1.4)
    if len(horizontals) < 2 or len(verticals) < 3:
        return None

    y_min = min((w.y0 for w in words), default=0.0)
    y_max = max((w.y1 for w in words), default=0.0)
    x_min = min((w.x0 for w in words), default=0.0)
    x_max = max((w.x1 for w in words), default=0.0)

    y_margin = 6.0
    x_margin = 6.0

    horizontals = [y for y in horizontals if (y_min - y_margin) <= y <= (y_max + y_margin)]
    verticals = [x for x in verticals if (x_min - x_margin) <= x <= (x_max + x_margin)]

    horizontals = _ensure_bounds(horizontals, y_min, y_max, pad=4.0)
    verticals = _ensure_bounds(verticals, x_min, x_max, pad=4.0)

    if len(horizontals) < 2 or len(verticals) < 3:
        return None

    return PageGeometry(page.number, horizontals, verticals)


def _cluster_positions(values: Iterable[float], *, tol: float) -> List[float]:
    ordered = sorted(float(v) for v in values)
    if not ordered:
        return []
    clusters: List[float] = [ordered[0]]
    for value in ordered[1:]:
        if abs(value - clusters[-1]) <= tol:
            clusters[-1] = (clusters[-1] + value) / 2.0
        else:
            clusters.append(value)
    return clusters


def _ensure_bounds(values: List[float], minimum: float, maximum: float, *, pad: float) -> List[float]:
    if not values:
        return []
    values = sorted(values)
    if minimum < values[0]:
        values.insert(0, minimum - pad)
    if maximum > values[-1]:
        values.append(maximum + pad)
    deduped: List[float] = []
    for value in values:
        if not deduped or abs(value - deduped[-1]) > 0.5:
            deduped.append(value)
    return deduped


def _rows_from_geometry(page_index: int, geo: PageGeometry, words: Sequence[Word]) -> List[Row]:
    row_bands = list(zip(geo.row_edges[:-1], geo.row_edges[1:]))
    col_bands = list(zip(geo.col_edges[:-1], geo.col_edges[1:]))
    if not row_bands or not col_bands:
        return []

    buckets: Dict[Tuple[int, int], List[Word]] = defaultdict(list)
    for word in words:
        text = word.text.strip()
        if not text:
            continue
        cx = (word.x0 + word.x1) / 2.0
        cy = (word.y0 + word.y1) / 2.0
        row_index = _find_band(row_bands, cy)
        col_index = _find_band(col_bands, cx)
        if row_index is None or col_index is None:
            continue
        buckets[(row_index, col_index)].append(word)

    rows: List[Row] = []
    for r_index, (y0, y1) in enumerate(row_bands):
        cells: List[Cell] = []
        has_text = False
        for c_index, (x0, x1) in enumerate(col_bands):
            bucket = buckets.get((r_index, c_index), [])
            if bucket:
                has_text = True
                sorted_words = sorted(bucket, key=lambda w: (w.y0, w.x0))
                raw = " ".join(w.text for w in sorted_words).strip()
                cell_x0 = min(w.x0 for w in bucket)
                cell_y0 = min(w.y0 for w in bucket)
                cell_x1 = max(w.x1 for w in bucket)
                cell_y1 = max(w.y1 for w in bucket)
            else:
                raw = ""
                cell_x0, cell_x1 = x0, x1
                cell_y0, cell_y1 = y0, y1
            cells.append(Cell(text=raw, x0=cell_x0, y0=cell_y0, x1=cell_x1, y1=cell_y1))
        if has_text:
            rows.append(Row(cells=cells, y0=y0, y1=y1, page=page_index))
    return rows


def _find_band(bands: Sequence[GridBand], coord: float) -> Optional[int]:
    for index, (start, end) in enumerate(bands):
        if start <= coord <= end:
            return index
    return None


def _collect_segments(page) -> Segments:
    segments: Segments = []

    def _add_segment(p0: Tuple[float, float], p1: Tuple[float, float]) -> None:
        segments.append((float(p0[0]), float(p0[1]), float(p1[0]), float(p1[1])))

    for drawing in page.get_drawings():
        for item in drawing.get("items", []):
            if not item:
                continue
            tag = item[0]
            if tag == "l" and len(item) >= 5:
                _, x0, y0, x1, y1 = item[:5]
                _add_segment((x0, y0), (x1, y1))
            elif tag == "re" and len(item) >= 2:
                rect = item[1]
                if hasattr(rect, "x0"):
                    x0, y0, x1, y1 = rect.x0, rect.y0, rect.x1, rect.y1
                else:
                    x0, y0, w, h = rect[:4]
                    x1, y1 = x0 + w, y0 + h
                _add_segment((x0, y0), (x1, y0))
                _add_segment((x1, y0), (x1, y1))
                _add_segment((x1, y1), (x0, y1))
                _add_segment((x0, y1), (x0, y0))
            elif tag == "qu" and len(item) >= 2:
                quad = item[1]
                try:
                    points = [(_pt.x, _pt.y) if hasattr(_pt, "x") else (float(_pt[0]), float(_pt[1])) for _pt in quad]
                except Exception:
                    continue
                if len(points) >= 4:
                    pts = points[:4]
                    for idx in range(4):
                        _add_segment(pts[idx], pts[(idx + 1) % 4])
    return segments


def _dump_debug(
    directory: Path,
    pdf_path: str,
    page_index: int,
    geometry: PageGeometry,
    rows: Sequence[Row],
) -> None:
    try:
        payload = {
            "pdf": Path(pdf_path).name,
            "page": page_index + 1,
            "row_edges": geometry.row_edges,
            "col_edges": geometry.col_edges,
            "rows": [
                {
                    "y0": row.y0,
                    "y1": row.y1,
                    "cells": [cell.text for cell in row.cells[:12]],
                }
                for row in rows[:40]
            ],
        }
        out_path = directory / f"{Path(pdf_path).stem}_page{page_index + 1}_grid.json"
        out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    except Exception:
        # Debug hooks must never break normal parsing.
        return
