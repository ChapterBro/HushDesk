from __future__ import annotations
import json, math
from pathlib import Path
from typing import Iterable, Iterator, List, Sequence
import pytest

try:
    import fitz  # PyMuPDF
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
                         header_text: str, footer_text: str, jitter: bool) -> None:
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
        for r_idx, row in enumerate(rows):
            _draw_row(page, row, xs, y + _row_jitter(r_idx, jitter, line_h))
            y += line_h
        page.insert_text(fitz.Point(180, 742), f"{footer_text} {page_index}", fontsize=10, fontname="helv")
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
