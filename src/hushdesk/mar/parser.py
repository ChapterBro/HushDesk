from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Dict, Iterable, List, Sequence, Tuple
import warnings

from hushdesk.pdf.engine_base import EngineUnavailable, Row
from hushdesk.pdf.layout import extract_rows
from hushdesk.pdf.timeparse import parse_time_token

from hushdesk.pdf.engines import MuPdfEngine, PdfMinerEngine


@dataclass
class ParseResult:
    rows: List[Row]
    records: List[Dict[str, object]]
    violations: List[Dict[str, object]]
    meta: Dict[str, object]
    fixture_payload: Dict[str, object]
    elapsed_seconds: float


EngineSpec = Tuple[str, type]


def parse_mar(path: str) -> ParseResult:
    engines: Sequence[EngineSpec] = (
        ("mupdf", MuPdfEngine),
        ("pdfminer", PdfMinerEngine),
    )
    last_error: Exception | None = None
    words = None
    engine_name = None
    warnings_list: List[str] = []

    start = perf_counter()
    for name, engine_cls in engines:
        try:
            engine = engine_cls()
            extracted = list(engine.extract_words(path))
            if not extracted:
                raise EngineUnavailable(f"{name} produced no words")
            words = extracted
            engine_name = name
            break
        except Exception as exc:  # pragma: no cover - exercised in fallback test
            last_error = exc
            warnings_list.append(_format_engine_warning(name, exc))
            continue

    if words is None or engine_name is None:
        if last_error is None:
            raise EngineUnavailable("Unable to extract words from PDF")
        if isinstance(last_error, EngineUnavailable):
            raise last_error
        raise EngineUnavailable("Unable to extract words from PDF") from last_error

    rows = extract_rows(words)
    matrix = rows_to_matrix(rows)
    records = _matrix_to_records(matrix)
    violations = _collect_violations(records)
    elapsed = perf_counter() - start
    pages = _infer_page_count(words)
    source_label = _fixture_source_label(path)

    meta: Dict[str, object] = {
        "engine": engine_name,
        "pages": pages,
        "rows": len(records),
        "elapsed_seconds": elapsed,
        "source": Path(path).name,
    }
    if warnings_list:
        meta["engine_warnings"] = list(warnings_list)
        for message in warnings_list:
            warnings.warn(message, RuntimeWarning, stacklevel=2)

    fixture_payload = _build_fixture_payload(records, violations, pages, source_label)

    return ParseResult(
        rows=rows,
        records=records,
        violations=violations,
        meta=meta,
        fixture_payload=fixture_payload,
        elapsed_seconds=elapsed,
    )


def rows_to_matrix(rows: Sequence[Row]) -> List[List[str]]:
    return [[cell.text for cell in row.cells] for row in rows]


def _matrix_to_records(matrix: Sequence[Sequence[str]]) -> List[Dict[str, object]]:
    records: List[Dict[str, object]] = []
    for row in matrix:
        if len(row) < 4:
            continue
        room, medication, am_raw, pm_raw = (row + ["", "", "", ""])[:4]
        record = {
            "room": _normalize_text(room),
            "medication": _normalize_text(medication),
            "am": _parse_slot(am_raw),
            "pm": _parse_slot(pm_raw),
        }
        records.append(record)
    return records


def _parse_slot(raw: str) -> Dict[str, object]:
    raw = _normalize_cell_text(raw)
    text = (raw or "").strip()
    if not text or text == "—":
        return {"time": None, "given": False, "raw": raw}
    normalized = parse_time_token(text)
    given = "✓" in text or "✔" in text
    return {
        "time": normalized,
        "given": given,
        "raw": raw,
    }


def _collect_violations(records: Sequence[Dict[str, object]]) -> List[Dict[str, object]]:
    violations: List[Dict[str, object]] = []
    for record in records:
        room = record.get("room")
        for slot_name in ("am", "pm"):
            slot = record.get(slot_name, {})
            if not isinstance(slot, dict):
                continue
            time = slot.get("time")
            given = slot.get("given")
            if time and not given:
                violations.append(
                    {"room": room, "slot": slot_name.upper(), "code": "missing_check"}
                )
    return violations


def _infer_page_count(words: Iterable) -> int:
    pages = {getattr(w, "page", 0) for w in words}
    return max(pages) + 1 if pages else 0


def _build_fixture_payload(
    records: Sequence[Dict[str, object]],
    violations: Sequence[Dict[str, object]],
    pages: int,
    source_label: str,
) -> Dict[str, object]:
    meta = {
        "pages": pages,
        "source": source_label,
        "canon_version": "v1",
        "engine": "fixture",
    }
    return {
        "meta": meta,
        "rows": list(records),
        "violations": list(violations),
    }


def _fixture_source_label(path: str) -> str:
    name = Path(path).stem.lower()
    if "synthetic" in name:
        return "synthetic"
    return Path(path).name


def _format_engine_warning(engine: str, exc: Exception) -> str:
    reason = str(exc) or "unknown error"
    return f"Engine '{engine}' unavailable ({reason}); falling back to alternate engine."


def _normalize_cell_text(raw: str) -> str:
    if raw is None:
        return ""
    text = str(raw)
    stripped = text.strip()
    middle_dot = "\u00b7"
    if stripped == middle_dot:
        return "—"
    if middle_dot in text:
        if any(ch.isdigit() for ch in stripped):
            text = text.replace(middle_dot, "✓")
        else:
            text = text.replace(middle_dot, "—")
    return text


def _normalize_text(value: str) -> str:
    return (value or "").strip()
