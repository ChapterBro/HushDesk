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
    date_col_index: int,
    date_str_us: str,
    hall: str,
    room: str,
    page_indices: Optional[List[int]] = None,
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
            if not day_bands or date_col_index >= len(day_bands):
                continue
            day_band = day_bands[date_col_index]

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
                    due_txt = _read(due_rect)
                    bp_txt = _read(bp_rect) if bp_rect else None
                    bp_tok, due_tok = _pick_bp_tokens(bp_txt, due_txt)
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
                            source={"page": pi + 1, "col": date_col_index + 1, "rules": rule_payload},
                        )
                    )

                # PM
                if "PM" in bands:
                    due_rect = cell_bbox(block, bands["PM"], day_band)
                    bp_rect = cell_bbox(block, bands["BP"], day_band) if "BP" in bands else None
                    due_txt = _read(due_rect)
                    bp_txt = _read(bp_rect) if bp_rect else None
                    bp_tok, due_tok = _pick_bp_tokens(bp_txt, due_txt)
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
                            source={"page": pi + 1, "col": date_col_index + 1, "rules": rule_payload},
                        )
                    )
        return out
    finally:
        doc.close()
