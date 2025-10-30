from __future__ import annotations
from typing import List
from hushdesk.pdf.layout import Row, extract_rows
from hushdesk.pdf.engines.mupdf_engine import MuPdfEngine

def _matrix(rows: List[Row]) -> List[List[str]]:
    return [[c.text for c in r.cells] for r in rows]

def test_words_are_bucketed_in_reading_order(synthetic_mar_pdf, synthetic_mar_matrix):
    engine = MuPdfEngine()
    words = list(engine.extract_words(str(synthetic_mar_pdf)))
    rows = extract_rows(words)
    assert _matrix(rows) == synthetic_mar_matrix
