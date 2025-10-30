from __future__ import annotations
import re
from typing import List, Dict, Optional, Tuple, Literal

from hushdesk.core.pdf.reader import open_pdf, page_text_in_rect, has_vector_x
from hushdesk.core.layout.blocks import detect_blocks, Block
from hushdesk.core.layout.tracks import calibrate_tracks
from hushdesk.core.layout.grid import detect_day_columns, cell_bbox
from hushdesk.core.parse.tokenizer import tokenize_cell_text
from hushdesk.core.rules.holds import parse_strict_rules
from hushdesk.core.engine.decide import decide_due, CellTokens, DecisionRecord

Track = Literal["AM","PM"]

_ROOM_LETTER = {"-1": "A", "-2": "B"}
_DAY_NAMES = {"SUN", "MON", "TUE", "WED", "THU", "FRI", "SAT"}

def _tok_from_text(s: str, has_hr_track: bool) -> CellTokens:
    t = tokenize_cell_text(s, has_hr_track=has_hr_track)
    return CellTokens(
        given=t.given,
        time=t.time,
        chart_code=t.chart_code,
        x_mark=t.x_mark,
        sbp=t.sbp,
        dbp=t.dbp,
        hr=t.hr,
    )

def _pick_bp_tokens(bp_txt: Optional[str], due_txt: str) -> Tuple[Optional[CellTokens], CellTokens]:
    bp_tok = _tok_from_text(bp_txt or "", has_hr_track=False) if bp_txt else None
    due_tok = _tok_from_text(due_txt, has_hr_track=False)
    return bp_tok, due_tok


def _clean_cell_text(text: str) -> str:
    if not text:
        return ""
    cleaned: List[str] = []
    for raw_line in text.splitlines():
        stripped = raw_line.strip()
        if not stripped:
            continue
        upper = stripped.upper()
        base = upper[:3]
        if base in _DAY_NAMES and (len(upper) == 3 or stripped[3:].strip().isdigit()):
            continue
        if stripped.isdigit():
            try:
                value = int(stripped)
            except ValueError:
                value = None
            if value is not None and 1 <= value <= 31:
                continue
        cleaned.append(stripped)
    return " ".join(cleaned)

def _block_matches_room(block: Block, room: str) -> bool:
    raw = (block.left_text or "").upper()
    canonical = room.upper()
    if canonical in raw:
        return True
    compact_target = canonical.replace("-", "")
    compact_text = raw.replace(" ", "").replace("-", "")
    if compact_target in compact_text:
        return True
    base = room.split("-")[0]
    suffix = room[room.rfind("-") :]
    letter = _ROOM_LETTER.get(suffix.upper(), "")
    if letter:
        alt = f"{base}{letter}"
        if alt in compact_text:
            return True
    return False

def extract_records_for_date(
    *,
    pdf_path: str,
    date_col_index: int | None,
    date_str_us: str,
    hall: str,
    room: str,
    page_indices: Optional[List[int]] = None,
    date_bands: Optional[Dict[int, Tuple[float, float]]] = None,
) -> List[DecisionRecord]:
    """
    Extract decisions for a specific (single) date column across all parametered blocks on given pages.
    Assumptions:
      - Vitals for parametered meds are guaranteed in the column (either BP track cell or due cell).
      - Tracks: AM and PM; some blocks may lack BP label; fallback to due cell text for vitals.
    """
    doc = open_pdf(pdf_path)
    try:
        pages = page_indices or list(range(len(doc)))
        out: List[DecisionRecord] = []

        for pi in pages:
            blocks = detect_blocks(doc, pi)
            if not blocks:
                continue
            day_bands = detect_day_columns(doc, pi)
            target_band: Optional[Tuple[float, float]] = None
            if date_bands and pi in date_bands:
                target_band = date_bands[pi]
            elif day_bands and date_col_index is not None and 0 <= date_col_index < len(day_bands):
                target_band = day_bands[date_col_index]
            if target_band is None:
                continue
            day_band = target_band

            col_number = 0
            if date_col_index is not None:
                col_number = date_col_index + 1
            else:
                try:
                    col_number = day_bands.index(day_band) + 1
                except ValueError:
                    col_number = 0

            for block in blocks:
                if not _block_matches_room(block, room):
                    continue
                rules = parse_strict_rules(block.rule_text)
                if not rules:
                    continue  # skip non-parametered
                rule_payload = [
                    {"metric": r.metric, "op": r.op, "threshold": r.threshold} for r in rules
                ]
                bands = calibrate_tracks(doc, pi, block)

                def _read(rect: Tuple[float, float, float, float]) -> str:
                    return page_text_in_rect(doc, pi, rect)

                # AM
                if "AM" in bands:
                    due_rect = cell_bbox(block, bands["AM"], day_band)
                    bp_rect = cell_bbox(block, bands["BP"], day_band) if "BP" in bands else None
                    due_txt_raw = _read(due_rect)
                    bp_txt_raw = _read(bp_rect) if bp_rect else None
                    bp_tok, due_tok = _pick_bp_tokens(
                        _clean_cell_text(bp_txt_raw) if bp_txt_raw else None,
                        _clean_cell_text(due_txt_raw),
                    )
                    if not due_tok.x_mark and has_vector_x(doc, pi, due_rect):
                        due_tok.x_mark = True
                    out.extend(
                        decide_due(
                            room=room,
                            hall=hall,
                            date=date_str_us,
                            track="AM",
                            rules=rules,
                            tokens_due=due_tok,
                            tokens_bp=bp_tok,
                            source={"page": pi + 1, "col": col_number, "rules": rule_payload},
                        )
                    )

                # PM
                if "PM" in bands:
                    due_rect = cell_bbox(block, bands["PM"], day_band)
                    bp_rect = cell_bbox(block, bands["BP"], day_band) if "BP" in bands else None
                    due_txt_raw = _read(due_rect)
                    bp_txt_raw = _read(bp_rect) if bp_rect else None
                    bp_tok, due_tok = _pick_bp_tokens(
                        _clean_cell_text(bp_txt_raw) if bp_txt_raw else None,
                        _clean_cell_text(due_txt_raw),
                    )
                    if not due_tok.x_mark and has_vector_x(doc, pi, due_rect):
                        due_tok.x_mark = True
                    out.extend(
                        decide_due(
                            room=room,
                            hall=hall,
                            date=date_str_us,
                            track="PM",
                            rules=rules,
                            tokens_due=due_tok,
                            tokens_bp=bp_tok,
                            source={"page": pi + 1, "col": col_number, "rules": rule_payload},
                        )
                    )
        return out
    finally:
        doc.close()
