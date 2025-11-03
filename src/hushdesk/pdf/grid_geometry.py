from __future__ import annotations

import json
import os
import re
from concurrent.futures import ProcessPoolExecutor, as_completed
from collections import defaultdict
from dataclasses import dataclass
from math import ceil
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional, Sequence, Tuple

from ._mupdf import import_fitz
from .engine_base import Cell, Row, Word

fitz = import_fitz(optional=True)  # type: ignore[assignment]

GridBand = Tuple[float, float]
Segments = List[Tuple[float, float, float, float]]

_DEBUG_ENV = "HUSHDESK_MAR_DEBUG_DIR"
_PARAM_CACHE: Dict[str, Dict[int, List["ParameterStrip"]]] = {}
_LINE_JOIN_TOL = 8.0
_HOTSPOT_KEYWORDS = ("SBP", "HOLD", "HR", "PULSE")
_PROGRESS_CB: Optional[Callable[[int, int], None]] = None
_ROOM_CANDIDATE = re.compile(r"\b([1-4]\d{2}(?:[- ]?[A-Z0-9])?)\b")


@dataclass
class PageGeometry:
    page_index: int
    row_edges: List[float]
    col_edges: List[float]


@dataclass
class ParameterStrip:
    page_index: int
    row_index: int
    y0: float
    y1: float
    x0: float
    x1: float
    text: str
    room: Optional[str] = None

    def to_meta(self) -> Dict[str, object]:
        return {
            "page": self.page_index,
            "row": self.row_index,
            "y0": self.y0,
            "y1": self.y1,
            "rect": (self.x0, self.y0, self.x1, self.y1),
            "text": self.text,
            "room": self.room,
        }


@dataclass(frozen=True)
class _PageTask:
    page_index: int
    words: List[Word]
    has_hotspot: bool


@dataclass(frozen=True)
class _ChunkTask:
    pdf_path: str
    tasks: List[_PageTask]


@dataclass(frozen=True)
class _PageResult:
    page_index: int
    rows: List[Row]
    strips: List[ParameterStrip]
    geometry: Optional[PageGeometry]


def install_progress_callback(callback: Optional[Callable[[int, int], None]]) -> None:
    """Register a callback invoked as pages finish geometry extraction."""
    global _PROGRESS_CB
    _PROGRESS_CB = callback


def _notify_progress(done: int, total: int) -> None:
    if total <= 0:
        total = 0
    cb = _PROGRESS_CB
    if cb is None:
        return
    try:
        cb(done, total)
    except Exception:
        # progress hooks must not break parsing
        return


def _normalize_strip_text(text: str) -> str:
    if not text:
        return ""
    lines: List[str] = []
    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        if not stripped:
            continue
        normalized = re.sub(r"\s+", " ", stripped)
        lines.append(normalized)
    return "\n".join(lines)


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

    cache_key = _cache_key(pdf_path)
    debug_dir = _debug_dir()
    rows_by_page: Dict[int, List[Row]] = {}
    param_cache: Dict[int, List[ParameterStrip]] = {}

    tasks: List[_PageTask] = []
    for page_index in sorted(words_by_page.keys()):
        words = words_by_page[page_index]
        if not words:
            continue
        hotspot = _page_has_hotspot(words)
        tasks.append(_PageTask(page_index=page_index, words=words, has_hotspot=hotspot))

    if not tasks:
        _PARAM_CACHE[cache_key] = {}
        return {}

    worker_count = _suggest_worker_count(len(tasks))
    chunks = _chunk_tasks(tasks, worker_count)
    total_pages = len(tasks)
    processed_pages = 0
    _notify_progress(0, total_pages)

    if worker_count <= 1:
        for chunk in chunks:
            chunk_results = _process_chunk(_ChunkTask(pdf_path=pdf_path, tasks=chunk))
            for result in chunk_results:
                _ingest_page_result(
                    result,
                    rows_by_page=rows_by_page,
                    param_cache=param_cache,
                    debug_dir=debug_dir,
                    pdf_path=pdf_path,
                )
                processed_pages += 1
                _notify_progress(processed_pages, total_pages)
    else:
        with ProcessPoolExecutor(max_workers=worker_count) as pool:
            futures = [
                pool.submit(_process_chunk, _ChunkTask(pdf_path=pdf_path, tasks=chunk))
                for chunk in chunks
            ]
            for future in as_completed(futures):
                page_results = future.result()
                for result in page_results:
                    _ingest_page_result(
                        result,
                        rows_by_page=rows_by_page,
                        param_cache=param_cache,
                        debug_dir=debug_dir,
                        pdf_path=pdf_path,
                    )
                    processed_pages += 1
                    _notify_progress(processed_pages, total_pages)

    if param_cache:
        _PARAM_CACHE[cache_key] = param_cache
    return rows_by_page


def _ingest_page_result(
    result: _PageResult,
    *,
    rows_by_page: Dict[int, List[Row]],
    param_cache: Dict[int, List[ParameterStrip]],
    debug_dir: Optional[Path],
    pdf_path: str,
) -> None:
    param_cache[result.page_index] = result.strips
    if result.rows:
        rows_by_page[result.page_index] = result.rows
        if debug_dir and result.geometry:
            _dump_debug(debug_dir, pdf_path, result.page_index, result.geometry, result.rows)
    elif result.page_index not in param_cache:
        param_cache[result.page_index] = result.strips


def _chunk_tasks(tasks: Sequence[_PageTask], worker_count: int) -> List[List[_PageTask]]:
    if not tasks:
        return []
    if worker_count <= 1:
        return [list(tasks)]
    chunk_size = max(1, ceil(len(tasks) / worker_count))
    return [list(tasks[i : i + chunk_size]) for i in range(0, len(tasks), chunk_size)]


def _suggest_worker_count(total_tasks: int) -> int:
    if total_tasks <= 1 or fitz is None:
        return 1
    override = os.getenv("HUSHDESK_MAR_WORKERS")
    if override:
        try:
            value = int(override)
        except ValueError:
            value = 0
        if value > 0:
            return min(total_tasks, value)
    cpu_count = os.cpu_count() or 1
    target = max(1, cpu_count - 1)
    return max(1, min(total_tasks, target))


def _process_chunk(chunk: _ChunkTask) -> List[_PageResult]:
    local_fitz = import_fitz(optional=True)
    if local_fitz is None:
        return [
            _PageResult(page_index=task.page_index, rows=[], strips=[], geometry=None)
            for task in chunk.tasks
        ]
    try:
        doc = local_fitz.open(chunk.pdf_path)
    except Exception:
        return [
            _PageResult(page_index=task.page_index, rows=[], strips=[], geometry=None)
            for task in chunk.tasks
        ]
    try:
        results: List[_PageResult] = []
        for task in chunk.tasks:
            if not task.words:
                results.append(
                    _PageResult(page_index=task.page_index, rows=[], strips=[], geometry=None)
                )
                continue
            try:
                page = doc.load_page(task.page_index)
            except Exception:
                results.append(
                    _PageResult(page_index=task.page_index, rows=[], strips=[], geometry=None)
                )
                continue
            geometry = _derive_page_geometry(page, task.words)
            if geometry is None:
                results.append(
                    _PageResult(page_index=task.page_index, rows=[], strips=[], geometry=None)
                )
                continue
            include_strips = task.has_hotspot
            rows, strips = _rows_from_geometry(
                task.page_index,
                geometry,
                task.words,
                include_parameter_strips=include_strips,
            )
            if not include_strips:
                strips = []
            results.append(
                _PageResult(
                    page_index=task.page_index,
                    rows=rows,
                    strips=strips,
                    geometry=geometry,
                )
            )
        return results
    finally:
        doc.close()


def _page_has_hotspot(words: Sequence[Word]) -> bool:
    if not words:
        return False
    for word in words:
        text = word.text.upper()
        if any(keyword in text for keyword in _HOTSPOT_KEYWORDS):
            return True
    return False


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


def _rows_from_geometry(
    page_index: int,
    geo: PageGeometry,
    words: Sequence[Word],
    *,
    include_parameter_strips: bool = True,
) -> Tuple[List[Row], List[ParameterStrip]]:
    row_bands = list(zip(geo.row_edges[:-1], geo.row_edges[1:]))
    col_bands = list(zip(geo.col_edges[:-1], geo.col_edges[1:]))
    if not row_bands or not col_bands:
        return [], []

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
    strips: List[ParameterStrip] = [] if include_parameter_strips else []
    grid_left_edge = geo.col_edges[0]
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
            room_hint = _room_hint_from_cells(cells)
            strip: Optional[ParameterStrip] = None
            if include_parameter_strips:
                strip = _parameter_strip_for_band(
                    page_index=page_index,
                    row_index=r_index,
                    band=(y0, y1),
                    words=words,
                    grid_left_edge=grid_left_edge,
                )
                if strip is None:
                    strip = ParameterStrip(
                        page_index=page_index,
                        row_index=r_index,
                        y0=y0,
                        y1=y1,
                        x0=grid_left_edge - 1.0,
                        x1=grid_left_edge - 1.0,
                        text="",
                    )
                if room_hint:
                    strip.room = room_hint
                strips.append(strip)
            meta = {"parameter_strip": strip.to_meta()} if (include_parameter_strips and strip and strip.text) else None
            rows.append(Row(cells=cells, y0=y0, y1=y1, page=page_index, meta=meta))
        elif include_parameter_strips:
            strips.append(
                ParameterStrip(
                    page_index=page_index,
                    row_index=r_index,
                    y0=y0,
                    y1=y1,
                    x0=grid_left_edge - 1.0,
                    x1=grid_left_edge - 1.0,
                    text="",
                )
            )
    return rows, strips


def _room_hint_from_cells(cells: Sequence[Cell]) -> Optional[str]:
    if not cells:
        return None
    raw = cells[0].text or ""
    if not raw:
        return None
    normalized = " ".join(raw.split())
    if not normalized:
        return None
    for match in _ROOM_CANDIDATE.finditer(normalized):
        token = match.group(1)
        if not token:
            continue
        upper = token.upper()
        if upper.startswith("ROOM"):
            continue
        return token
    return None


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


def parameter_strips(pdf_path: str, page_index: Optional[int] = None) -> Dict[int, List[ParameterStrip]] | List[ParameterStrip]:
    cache = _ensure_parameter_strips(pdf_path, force_page=page_index)
    if page_index is None:
        return cache
    return cache.get(page_index, [])


def _parameter_strip_for_band(
    page_index: int,
    row_index: int,
    band: GridBand,
    words: Sequence[Word],
    grid_left_edge: float,
) -> Optional[ParameterStrip]:
    margin = 1.5
    band_y0, band_y1 = band
    left_limit = grid_left_edge - 2.0
    candidates: List[Word] = []
    for word in words:
        cy = (word.y0 + word.y1) / 2.0
        if cy < band_y0 - margin or cy > band_y1 + margin:
            continue
        if word.x1 > left_limit:
            continue
        if not word.text.strip():
            continue
        candidates.append(word)
    if not candidates:
        return None
    candidates.sort(key=lambda w: (w.y0, w.x0))
    lines: List[List[Word]] = []
    for word in candidates:
        if not lines:
            lines.append([word])
            continue
        last_line = lines[-1]
        last_center = (last_line[-1].y0 + last_line[-1].y1) / 2.0
        current_center = (word.y0 + word.y1) / 2.0
        if abs(current_center - last_center) <= _LINE_JOIN_TOL:
            last_line.append(word)
        else:
            lines.append([word])
    text_lines: List[str] = []
    for line in lines:
        sorted_line = sorted(line, key=lambda w: w.x0)
        text_lines.append(" ".join(w.text for w in sorted_line).strip())
    text = "\n".join(t for t in text_lines if t)
    text = _normalize_strip_text(text)
    if not text:
        return None
    x0 = min(w.x0 for w in candidates)
    y0 = min(w.y0 for w in candidates)
    x1 = max(w.x1 for w in candidates)
    y1 = max(w.y1 for w in candidates)
    return ParameterStrip(
        page_index=page_index,
        row_index=row_index,
        y0=y0,
        y1=y1,
        x0=x0,
        x1=x1,
        text=text,
    )


def _cache_key(path: str) -> str:
    try:
        return str(Path(path).resolve())
    except Exception:
        return path


def _ensure_parameter_strips(pdf_path: str, force_page: Optional[int] = None) -> Dict[int, List[ParameterStrip]]:
    key = _cache_key(pdf_path)
    existing = _PARAM_CACHE.get(key)
    if existing is not None:
        if force_page is None:
            return existing
        if existing.get(force_page):
            return existing
    if fitz is None:
        cache = existing or {}
        _PARAM_CACHE[key] = cache
        return cache
    try:
        doc = fitz.open(pdf_path)
    except Exception:
        cache = existing or {}
        _PARAM_CACHE[key] = cache
        return cache
    try:
        words_by_page: Dict[int, List[Word]] = {}
        for page_index in range(len(doc)):
            page = doc.load_page(page_index)
            raw_words = page.get_text("words") or []
            words: List[Word] = []
            for item in raw_words:
                if not item or len(item) < 5:
                    continue
                x0, y0, x1, y1, text = item[:5]
                words.append(Word(float(x0), float(y0), float(x1), float(y1), str(text), page_index))
            words_by_page[page_index] = words
        extract_grid_rows(pdf_path, words_by_page)
        cache = _PARAM_CACHE.get(key, {}) if existing is None else existing
        if cache is None:
            cache = {}
        for page_index, page_words in words_by_page.items():
            if force_page is not None and page_index != force_page:
                if cache.get(page_index):
                    continue
            strips = cache.get(page_index, [])
            if strips:
                continue
            fallback = _fallback_parameter_strips(page_words, page_index)
            if fallback:
                cache.setdefault(page_index, []).extend(fallback)
        _PARAM_CACHE[key] = cache
    finally:
        doc.close()
    return _PARAM_CACHE.get(key, existing or {}) or {}


def _fallback_parameter_strips(words: Sequence[Word], page_index: int) -> List[ParameterStrip]:
    usable = [w for w in words if w.text.strip()]
    if not usable:
        return []
    heights = [w.height for w in usable if w.height > 0]
    if heights:
        heights.sort()
        median = heights[len(heights) // 2]
    else:
        median = 10.0
    y_tol = max(median * 0.6, 4.0)
    buckets: Dict[int, List[Word]] = defaultdict(list)
    for word in usable:
        bucket = int(round(word.y0 / y_tol))
        buckets[bucket].append(word)
    if not buckets:
        return []
    min_x = min(word.x0 for word in usable)
    room_header = next((w.x0 for w in usable if w.text.strip().lower() == "room"), None)
    if room_header is not None and room_header > min_x:
        threshold = room_header + 120.0
    else:
        threshold = min_x + 120.0
    strips: List[ParameterStrip] = []
    active: Optional[ParameterStrip] = None
    row_index = 0
    for bucket_key in sorted(buckets):
        segment = buckets[bucket_key]
        y0 = min(w.y0 for w in segment)
        y1 = max(w.y1 for w in segment)
        left_words: List[Word] = []
        for word in segment:
            if word.x0 > threshold:
                continue
            token = word.text.strip()
            if not token:
                continue
            upper_tok = token.upper()
            if upper_tok in {"ROOM", "RESIDENT", "AM", "PM", "HS"}:
                continue
            cleaned = token.replace(" ", "")
            if any(ch.isalpha() for ch in cleaned) and any(ch.isdigit() for ch in cleaned):
                continue
            if ("-" in cleaned or "/" in cleaned) and cleaned.replace("-", "").replace("/", "").isdigit():
                continue
            left_words.append(word)
        if not left_words:
            continue
        left_words.sort(key=lambda w: (w.y0, w.x0))
        lines: List[List[Word]] = []
        for word in left_words:
            if not lines:
                lines.append([word])
                continue
            last_line = lines[-1]
            last_center = (last_line[-1].y0 + last_line[-1].y1) / 2.0
            current_center = (word.y0 + word.y1) / 2.0
            if abs(current_center - last_center) <= _LINE_JOIN_TOL:
                last_line.append(word)
            else:
                lines.append([word])
        text_lines: List[str] = []
        for line in lines:
            text_lines.append(" ".join(w.text for w in sorted(line, key=lambda w: w.x0)).strip())
        text = "\n".join(t for t in text_lines if t)
        text = _normalize_strip_text(text)
        if not text:
            continue
        upper = text.upper()
        has_keyword = any(key in upper for key in ("SBP", "HOLD", "PULSE", "HR"))
        x0 = min(w.x0 for w in left_words)
        x1 = max(w.x1 for w in left_words)
        if has_keyword:
            if active:
                active.row_index = row_index
                strips.append(active)
                row_index += 1
            active = ParameterStrip(
                page_index=page_index,
                row_index=row_index,
                y0=y0,
                y1=y1,
                x0=x0,
                x1=x1,
                text=text,
            )
        elif active and (y0 - active.y1) <= max(y_tol, 18.0):
            active.text = _normalize_strip_text("\n".join([active.text, text]))
            active.y0 = min(active.y0, y0)
            active.y1 = max(active.y1, y1)
            active.x0 = min(active.x0, x0)
            active.x1 = max(active.x1, x1)
        else:
            if active:
                active.row_index = row_index
                strips.append(active)
                row_index += 1
            active = None
    if active:
        active.row_index = row_index
        strips.append(active)
    return strips
