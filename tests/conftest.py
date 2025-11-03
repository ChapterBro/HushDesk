from __future__ import annotations
import json, math
from pathlib import Path
from typing import Iterable, Iterator, List, Sequence
import pytest

from hushdesk.pdf._mupdf import import_fitz

try:
    fitz = import_fitz(optional=True)  # PyMuPDF
except Exception:  # pragma: no cover
    fitz = None

_HEADER_ROW = ["Room", "Medication", "AM", "PM"]
_BASE_DATA_ROWS = [
    ["101A", "Med One",  "08:00 ✓", "20:00 !"],
    ["102B", "Med Two",  "08:00 ✓", "—"],
    ["201A", "Med Three","06:00 ✓", "18:00 ✓"],
    ["202B", "Med Four", "—",       "22:00 !"],
]

@pytest.fixture(scope="session")
def synthetic_fixture_payload() -> dict:
    payload_path = Path(__file__).parent / "data" / "synthetic_fixture.json"
    with payload_path.open("r", encoding="utf-8") as f:
        return json.load(f)

@pytest.fixture(scope="session")
def synthetic_mar_matrix() -> List[List[str]]:
    return [list(r) for r in _BASE_DATA_ROWS]

@pytest.fixture(scope="session")
def synthetic_mar_pdf(tmp_path_factory: pytest.TempPathFactory) -> Path:
    if fitz is None:
        pytest.skip("PyMuPDF not installed; synthetic PDF generation requires fitz")
    out = tmp_path_factory.mktemp("pdfs") / "synthetic_mar.pdf"
    if out.exists():
        return out
    _write_synthetic_pdf(
        out,
        pages=[_BASE_DATA_ROWS[:2], _BASE_DATA_ROWS[2:]],
        header_text="Synthetic Header",
        footer_text="Synthetic Footer",
        jitter=False,
    )
    return out

@pytest.fixture(scope="session")
def jittered_two_column_pdf(tmp_path_factory: pytest.TempPathFactory) -> Path:
    if fitz is None:
        pytest.skip("PyMuPDF not installed; synthetic PDF generation requires fitz")
    out = tmp_path_factory.mktemp("pdfs") / "jittered_columns.pdf"
    if out.exists():
        return out
    top = _with_jitter(_BASE_DATA_ROWS[:2], jitter=True)
    bottom = _with_jitter(_BASE_DATA_ROWS[2:], jitter=True)
    _write_synthetic_pdf(
        out, pages=[top, bottom],
        header_text="Header Repeated",
        footer_text="Footer Repeated",
        jitter=True,
    )
    return out

@pytest.fixture(scope="session")
def header_footer_pdf(tmp_path_factory: pytest.TempPathFactory) -> Path:
    if fitz is None:
        pytest.skip("PyMuPDF not installed; synthetic PDF generation requires fitz")
    out = tmp_path_factory.mktemp("pdfs") / "header_footer.pdf"
    if out.exists():
        return out
    rows = [_BASE_DATA_ROWS[0], _BASE_DATA_ROWS[1]]
    _write_synthetic_pdf(
        out, pages=[rows],
        header_text="Remove Me Header",
        footer_text="Remove Me Footer",
        jitter=False,
    )
    return out

@pytest.fixture(scope="session")
def parameter_rules_pdf(tmp_path_factory: pytest.TempPathFactory) -> Path:
    if fitz is None:
        pytest.skip("PyMuPDF not installed; synthetic PDF generation requires fitz")
    out = tmp_path_factory.mktemp("pdfs") / "parameter_rules.pdf"
    if out.exists():
        return out
    rows_page = [
        ["101A", "Lisinopril", "06:00 ✓", "18:00 ✓"],
        ["202B", "Metoprolol", "—", "20:00 !"],
        ["303C", "Furosemide", "—", "—"],
    ]
    left_text = [
        "Hold for SBP less\nthan 90",
        "Hold for SBP greater than 160",
        "",
    ]
    _write_synthetic_pdf(
        out,
        pages=[rows_page],
        header_text="Param Header",
        footer_text="Footer",
        jitter=False,
        left_text_pages=[left_text],
        draw_grid=True,
    )
    return out

@pytest.fixture(scope="session")
def monthly_mar_pdf(tmp_path_factory: pytest.TempPathFactory) -> Path:
    if fitz is None:
        pytest.skip("PyMuPDF not installed; synthetic PDF generation requires fitz")
    out = tmp_path_factory.mktemp("pdfs") / "monthly_mar.pdf"
    if out.exists():
        out.unlink()
    _write_monthly_pdf(out)
    return out

def _with_jitter(rows: Sequence[Sequence[str]], jitter: bool) -> List[List[str]]:
    if not jitter:
        return [list(r) for r in rows]
    # introduce slight y jitter marker (text unchanged; jitter applied in draw)
    return [list(r) for r in rows]

def _row_jitter(idx: int, jitter: bool, h: float) -> float:
    if not jitter:
        return 0.0
    amp = h * 0.15
    return amp * math.sin(idx)

def _draw_row(page: "fitz.Page", row: Sequence[str], xs: Sequence[float], y: float) -> None:
    for i, cell in enumerate(row):
        page.insert_text(fitz.Point(xs[i], y), cell, fontsize=12, fontname="helv")

def _write_synthetic_pdf(path: Path, pages: Iterable[Iterable[Sequence[str]]],
                         header_text: str, footer_text: str, jitter: bool,
                         left_text_pages: Optional[Sequence[Sequence[str]]] = None,
                         draw_grid: bool = False) -> None:
    assert fitz is not None, "PyMuPDF required to synthesize PDFs in tests"
    doc = fitz.open()
    xs = [72.0, 220.0, 360.0, 480.0]
    header_base = 72.0
    line_h = 20.0
    for page_index, rows in enumerate(pages, start=1):
        page = doc.new_page()
        page.insert_text(fitz.Point(120, header_base - 32), header_text, fontsize=12, fontname="helv")
        y = header_base
        _draw_row(page, _HEADER_ROW, xs, y)
        y += line_h
        if draw_grid:
            grid_left = 60.0
            col_widths = [140.0, 200.0, 120.0, 120.0]
            total_width = sum(col_widths)
            row_count = len(rows) + 1
            grid_top = y - 6.0
            grid_bottom = grid_top + row_count * line_h
            x_positions = [grid_left]
            for width in col_widths:
                x_positions.append(x_positions[-1] + width)
            for idx in range(row_count + 1):
                line_y = grid_top + idx * line_h
                page.draw_line(
                    fitz.Point(grid_left, line_y),
                    fitz.Point(grid_left + total_width, line_y),
                    color=(0, 0, 0),
                    width=0.5,
                )
            for x_pos in x_positions:
                page.draw_line(
                    fitz.Point(x_pos, grid_top),
                    fitz.Point(x_pos, grid_bottom),
                    color=(0, 0, 0),
                    width=0.5,
                )
        left_rows = left_text_pages[page_index - 1] if left_text_pages and page_index - 1 < len(left_text_pages) else None
        for r_idx, row in enumerate(rows):
            if left_rows:
                left_text = left_rows[r_idx] if r_idx < len(left_rows) else ""
                if left_text:
                    base_y = y + _row_jitter(r_idx, jitter, line_h)
                    for line_offset, chunk in enumerate(str(left_text).splitlines()):
                        page.insert_text(
                            fitz.Point(36.0, base_y + line_offset * 10.0),
                            chunk,
                            fontsize=11,
                            fontname="helv",
                        )
            _draw_row(page, row, xs, y + _row_jitter(r_idx, jitter, line_h))
            y += line_h
        page.insert_text(fitz.Point(180, 742), f"{footer_text} {page_index}", fontsize=10, fontname="helv")
    doc.save(path)
    doc.close()

def _write_monthly_pdf(path: Path) -> None:
    assert fitz is not None, "PyMuPDF required to synthesize PDFs in tests"
    doc = fitz.open()
    page = doc.new_page(width=612, height=792)

    # Header with hall reference
    page.insert_text(fitz.Point(200, 72), "Bridgeman Hall Monthly MAR", fontsize=14, fontname="helv")
    page.insert_text(fitz.Point(200, 90), "October 2025", fontsize=12, fontname="helv")

    block_x = 60.0
    grid_top = 120.0
    row_height = 12.0
    col_width = 72.0
    cols = 3
    rows = 4  # header + AM + PM + BP
    grid_left = block_x + 132.0
    grid_bottom = grid_top + row_height * rows
    grid_right = grid_left + col_width * cols

    # Draw column lines (vertical)
    for idx in range(cols + 1):
        x = grid_left + (idx * col_width)
        page.draw_line(fitz.Point(x, grid_top), fitz.Point(x, grid_bottom), color=(0, 0, 0), width=1)
    # Draw row separators (horizontal)
    for idx in range(rows + 1):
        y = grid_top + (idx * row_height)
        page.draw_line(fitz.Point(grid_left, y), fitz.Point(grid_right, y), color=(0, 0, 0), width=1)

    # Day headers
    day_names = ["Tue", "Wed", "Thu"]
    for idx, day in enumerate((28, 29, 30)):
        x = grid_left + idx * col_width + 18
        page.insert_text(fitz.Point(x, grid_top + 4), day_names[idx], fontsize=8, fontname="helv")
        page.insert_text(fitz.Point(x, grid_top + 9), str(day), fontsize=10, fontname="helv")

    # Left block content with rules and track labels
    page.insert_text(fitz.Point(block_x, grid_top - 24), "Room 307-2", fontsize=11, fontname="helv")
    page.insert_text(fitz.Point(block_x, grid_top - 14), "Metoprolol 25 mg by mouth", fontsize=11, fontname="helv")
    page.insert_text(fitz.Point(block_x, grid_top - 4), "SBP < 110", fontsize=11, fontname="helv")
    page.insert_text(fitz.Point(block_x, grid_top + 6), "AM", fontsize=11, fontname="helv")
    page.insert_text(fitz.Point(block_x, grid_top + 16), "PM", fontsize=11, fontname="helv")
    page.insert_text(fitz.Point(block_x, grid_top + 26), "BP", fontsize=11, fontname="helv")

    # Due cell content for AM row (row index 1) in day 30 column to trigger HOLD-MISS
    am_text_point = fitz.Point(grid_left + 2 * col_width + 6, grid_top + row_height - 5)
    page.insert_text(am_text_point, "07:00 100/60", fontsize=8, fontname="helv")
    # Add filler text in earlier day columns for balance
    page.insert_text(fitz.Point(grid_left + 6, grid_top + row_height - 5), "—", fontsize=8, fontname="helv")
    page.insert_text(fitz.Point(grid_left + col_width + 6, grid_top + row_height - 5), "—", fontsize=8, fontname="helv")
    # BP measurement row for context
    bp_text_point = fitz.Point(grid_left + 2 * col_width + 8, grid_top + row_height * 3 + 6)
    page.insert_text(bp_text_point, "100/60", fontsize=8, fontname="helv")

    # Footer mention of hall for detection reinforcement
    page.insert_text(fitz.Point(200, 742), "Bridgeman - Chart Codes Legend", fontsize=10, fontname="helv")

    doc.save(path)
    doc.close()

# Optional capture hook used by canon tests
@pytest.fixture
def capture_canon_rows(monkeypatch: pytest.MonkeyPatch) -> Iterator[List[List[str]]]:
    captured: List[List[str]] = []
    def _capture(rows):
        captured.extend([list(r) for r in rows])
    monkeypatch.setattr("hushdesk.pdf.canon._debug_capture_rows", _capture, raising=False)
    yield captured
