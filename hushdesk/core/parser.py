"""PDF parser capable of streaming large MAR documents."""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
import logging
import re
from typing import Dict, List, Optional

try:
    import pdfplumber
except ModuleNotFoundError:  # pragma: no cover - fallback when dependency missing
    pdfplumber = None

from . import rules
from .building_master import hall_for_room, is_valid_room, normalize_room
from .models import Rule, Vital
from .timeutil import combine_ct, parse_time_token

LOGGER = logging.getLogger(__name__)


DAY_NUMBER_RE = re.compile(r"^(\d{1,2})$")
TICK_RE = re.compile(r"^[✓✔]$")
TIME_RE = re.compile(r"\b(?:[01]?\d|2[0-3]):?[0-5]\d\b")
VITAL_RE = re.compile(
    r"\b(?P<metric>SBP|HR|Pulse)\s*(?:[:=])?\s*(?P<value>\d{2,3})\s*@\s*(?P<time>(?:[01]?\d|2[0-3]):?[0-5]\d)"
)
ROOM_TOKEN_RE = re.compile(r"\b(\d{3}[AB]?)\b")



class SimplePage:
    def __init__(self, words, text):
        self.width = 612
        self.height = 792
        self._words = words
        self._text = text

    def extract_words(self, keep_blank_chars: bool = False):
        return self._words

    def extract_text(self):
        return self._text


def _simple_pdf_pages(path: str):
    from pathlib import Path as _Path

    content = _Path(path).read_text(encoding="latin-1")
    streams = re.findall(r"stream\n(.*?)endstream", content, re.DOTALL)
    pages = []
    for stream in streams:
        words = []
        texts = []
        for match in re.finditer(r"1 0 0 1 ([0-9.]+) ([0-9.]+) Tm \((.*?)\) Tj", stream):
            x = float(match.group(1))
            y = float(match.group(2))
            raw = match.group(3)
            text_value = bytes(raw, "latin-1").decode("utf-8")
            width = max(6.0 * len(text_value), 6.0)
            top = 792 - y
            bottom = top + 12
            words.append({
                "text": text_value,
                "x0": x,
                "x1": x + width,
                "top": top,
                "bottom": bottom,
            })
            texts.append(text_value)
        pages.append(SimplePage(words, "\n".join(texts)))

    return pages


@dataclass
class ParsedDose:
    room: str
    rule: Rule | None
    rule_error: Optional[str]
    med_name: Optional[str]
    time_local: datetime
    admin: str
    vitals: List[Vital]
    flags: List[str]


@dataclass
class ParseResult:
    doses: List[ParsedDose]
    meta: Dict[str, object]


def _detect_day_columns(page) -> List[Dict[str, object]]:
    words = page.extract_words(keep_blank_chars=False)
    top_limit = page.height * 0.18
    columns: List[Dict[str, object]] = []
    for word in words:
        if word["top"] > top_limit:
            continue
        text = word["text"].strip()
        match = DAY_NUMBER_RE.match(text)
        if match:
            day = int(match.group(1))
            columns.append({
                "day": day,
                "x0": word["x0"],
                "x1": word["x1"],
            })
    columns.sort(key=lambda item: item["x0"])
    return columns


def _group_words_by_line(words: List[Dict[str, object]], tolerance: float = 3.0) -> List[List[Dict[str, object]]]:
    lines: List[List[Dict[str, object]]] = []
    for word in sorted(words, key=lambda w: (w["top"], w["x0"])):
        placed = False
        for line in lines:
            if abs(line[0]["top"] - word["top"]) <= tolerance:
                line.append(word)
                placed = True
                break
        if not placed:
            lines.append([word])
    for line in lines:
        line.sort(key=lambda w: w["x0"])
    return lines


def _extract_med_box_lines(page, columns: List[Dict[str, object]]):
    words = page.extract_words(keep_blank_chars=False)
    if not columns:
        return []
    left_edge = min(col["x0"] for col in columns)
    med_words = [w for w in words if w["x1"] <= left_edge]
    return _group_words_by_line(med_words)


def _extract_med_name(line_text: str) -> Optional[str]:
    parts = [segment.strip() for segment in re.split(r"SBP|HR|Pulse", line_text, flags=re.IGNORECASE)]
    if parts:
        candidate = parts[0].strip("-•: ")
        if candidate and not candidate.isdigit():
            return candidate
    return None


def _extract_vitals(page, audit_date: datetime) -> Dict[str, List[Vital]]:
    full_text = page.extract_text() or ""
    vitals: Dict[str, List[Vital]] = defaultdict(list)
    for match in VITAL_RE.finditer(full_text):
        metric = match.group("metric").upper()
        if metric == "PULSE":
            metric = "HR"
        value = int(match.group("value"))
        time_token = match.group("time")
        parsed = parse_time_token(time_token)
        if not parsed:
            continue
        taken_at = combine_ct(audit_date.date(), parsed)
        vitals[metric].append(Vital(metric=metric, value=value, taken_at=taken_at))
    return vitals


def _extract_room(page) -> Optional[str]:
    words = page.extract_words(keep_blank_chars=False)
    candidates = []
    for word in sorted(words, key=lambda w: (w["top"], -w["x0"])):
        text = word["text"].strip()
        if "/" in text:
            continue
        match = ROOM_TOKEN_RE.search(text)
        if match:
            normalized = normalize_room(match.group(1))
            if normalized:
                candidates.append(normalized)
    for candidate in candidates:
        if is_valid_room(candidate):
            return candidate
    return None


def parse_document(path: str, audit_date: datetime) -> ParseResult:
    selected_day = audit_date.day
    doses: List[ParsedDose] = []
    available_columns: List[int] = []
    pages_parsed = 0
    pages_used = 0
    hall_counter: Counter[str] = Counter()
    flags: List[str] = []
    if pdfplumber:
        pdf = pdfplumber.open(path)
        pages_iter = pdf.pages
    else:
        pdf = None
        pages_iter = _simple_pdf_pages(path)
    try:
        for page in pages_iter:
            pages_parsed += 1
            columns = _detect_day_columns(page)
            if not columns:
                continue
            available_columns = sorted({col["day"] for col in columns} | set(available_columns))
            col_map = {col["day"]: col for col in columns}
            if selected_day not in col_map:
                continue
            pages_used += 1
            med_lines = _extract_med_box_lines(page, columns)
            if not med_lines:
                continue
            day_column = col_map[selected_day]
            room = _extract_room(page)
            if room and is_valid_room(room):
                hall = hall_for_room(room)
                if hall:
                    hall_counter[hall[0]] += 1
            vitals_map = _extract_vitals(page, audit_date)
            page_words = page.extract_words(keep_blank_chars=False)
            for line in med_lines:
                line_text = " ".join(word["text"] for word in line)
                parsed_rule = rules.parse_rule(line_text)
                rule_obj: Rule | None
                rule_error = None
                if isinstance(parsed_rule, Rule):
                    rule_obj = parsed_rule
                else:
                    rule_obj = None
                    rule_error = parsed_rule.get('error') if isinstance(parsed_rule, dict) else None
                med_name = _extract_med_name(line_text)
                if not rule_obj and "SBP" not in line_text.upper() and "HR" not in line_text.upper():
                    continue
                # gather marks for selected day
                y0 = min(word["top"] for word in line)
                y1 = max(word["bottom"] for word in line)
                column_words = [
                    w for w in page_words
                    if y0 - 2 <= w["top"] <= y1 + 2 and day_column["x0"] <= w["x0"] <= day_column["x1"] + 80
                ]
                if not column_words:
                    continue
                admin_state = "UNKNOWN"
                held_marker = False
                marks = []
                for word in column_words:
                    text = word['text'].strip()
                    upper = text.upper()
                    if TICK_RE.match(text):
                        admin_state = 'GIVEN'
                    if 'HOLD' in upper:
                        held_marker = True
                    marks.append(text)
                if held_marker and admin_state != 'GIVEN':
                    admin_state = 'NOT_GIVEN_HELD'
                time_tokens = [tok for tok in marks if TIME_RE.search(tok)]
                times = []
                for token in time_tokens:
                    parsed_time = parse_time_token(token)
                    if parsed_time:
                        times.append(parsed_time)
                if not times:
                    continue
                for when in times:
                    time_local = combine_ct(audit_date.date(), when)
                    vitals: List[Vital] = []
                    stale = False
                    for metric, window in (("SBP", timedelta(minutes=30)), ("HR", timedelta(minutes=30))):
                        entries = vitals_map.get(metric, [])
                        best = None
                        best_delta = timedelta.max
                        for entry in entries:
                            delta = abs(entry.taken_at - time_local)
                            if delta <= window and delta < best_delta:
                                best = entry
                                best_delta = delta
                        if not best and entries:
                            for entry in entries:
                                delta = abs(entry.taken_at - time_local)
                                if delta <= timedelta(minutes=120) and delta < best_delta:
                                    best = entry
                                    best_delta = delta
                                    stale = True
                        if best:
                            vitals.append(best)
                        else:
                            stale = True
                    local_flags = []
                    if stale:
                        local_flags.append("vitals_stale")
                    doses.append(
                        ParsedDose(
                            room=room or '000-1',
                            rule=rule_obj,
                            rule_error=rule_error,
                            med_name=med_name,
                            time_local=time_local,
                            admin=admin_state,
                            vitals=vitals,
                            flags=local_flags,
                        )
                    )
    finally:
        if pdfplumber and pdf is not None:
            pdf.close()
    hall_name = None
    hall_short = None
    if hall_counter:
        hall_name = hall_counter.most_common(1)[0][0]
        first_room = next((dose.room for dose in doses if is_valid_room(dose.room)), None)
        if first_room:
            hall_info = hall_for_room(first_room)
            if hall_info:
                hall_name, hall_short = hall_info
    meta = {
        "selected_day": selected_day,
        "available_columns": available_columns,
        "file_date_guess": None,
        "pages_parsed": pages_parsed,
        "pages_used": pages_used,
        "hall_name": hall_name,
        "hall_short": hall_short,
        "flags": flags,
    }
    return ParseResult(doses=doses, meta=meta)
