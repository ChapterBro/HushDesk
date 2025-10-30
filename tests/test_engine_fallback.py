from __future__ import annotations
import pytest
from hushdesk.mar import parser as mar_parser

@pytest.mark.usefixtures("synthetic_mar_pdf")
def test_pdfminer_fallback_matches_primary(monkeypatch, synthetic_mar_pdf, synthetic_mar_matrix):
    primary = mar_parser.parse_mar(str(synthetic_mar_pdf))
    primary_matrix = mar_parser.rows_to_matrix(primary.rows)

    def _unavailable(*args, **kwargs):
        raise mar_parser.EngineUnavailable("MuPDF not available")

    monkeypatch.setattr(
        "hushdesk.pdf.engines.mupdf_engine.MuPdfEngine.extract_words",
        lambda self, path: _unavailable(),
        raising=True,
    )
    fallback = mar_parser.parse_mar(str(synthetic_mar_pdf))
    fallback_matrix = mar_parser.rows_to_matrix(fallback.rows)

    assert primary_matrix == synthetic_mar_matrix
    assert fallback_matrix == synthetic_mar_matrix
    assert fallback.meta.get("engine") == "pdfminer"
