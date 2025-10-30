from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional

from .celljoin import join_tokens
from .header_scrub import scrub_header
from .mar_blocks import MarBlock, find_mar_blocks
from .timeparse import TimeNorm, normalize_time_token

try:
    from .pdfio import extract_text_by_page  # type: ignore
except Exception:  # pragma: no cover - optional dependency hook

    def extract_text_by_page(path: str) -> List[List[str]]:
        raise RuntimeError("pdfio.extract_text_by_page not available")


@dataclass
class Dose:
    med: str
    raw_time: str
    normalized_time: Optional[str]
    time_range: Optional[str]
    slot: Optional[str]
    cell: str


@dataclass
class ParseResult:
    doses: List[Dose]
    meta: Dict[str, str]  # non-identifying metadata only
    notes: List[str]  # parsing notes/warnings


def _is_med_head(ln: str) -> bool:
    return "Give" in ln and "by mouth" in ln


def _is_time_row(ln: str) -> bool:
    keys = ("AM", "PM", "HS", "0800", "0600", "0700", "2100", "8pm-1", "6a-10", "11a -", "12p-2", "4pm-7")
    return any(k in ln for k in keys)


def _tokenize_cell(line: str) -> List[str]:
    # Basic whitespace tokenization; downstream join_tokens will normalize.
    return [tok for tok in line.split(" ") if tok]


def parse_mar_pdf(path: str) -> ParseResult:
    pages = extract_text_by_page(path)
    if not pages:
        raise ValueError("no pages extracted")

    blocks: List[MarBlock] = find_mar_blocks(pages)
    if not blocks:
        raise ValueError("no schedule grid found")

    doses: List[Dose] = []
    notes: List[str] = []
    meta: Dict[str, str] = {"pages": str(len(pages))}

    for block in blocks:
        lines = scrub_header(block.lines)
        current_med: Optional[str] = None
        for ln in lines:
            text = ln.strip()
            if not text:
                continue
            if _is_med_head(text):
                current_med = text.split("Give", 1)[0].strip() or "Medication"
                continue
            if current_med and _is_time_row(text):
                tn: TimeNorm = normalize_time_token(text)
                cell_tokens = _tokenize_cell(text)
                cell_value = join_tokens(cell_tokens)
                doses.append(
                    Dose(
                        med=current_med,
                        raw_time=tn.raw_time,
                        normalized_time=tn.normalized_time,
                        time_range=tn.time_range,
                        slot=tn.slot,
                        cell=cell_value,
                    )
                )

    if not doses:
        notes.append("Found MAR structure but no dose rows; review time row heuristics.")
    return ParseResult(doses=doses, meta=meta, notes=notes)

