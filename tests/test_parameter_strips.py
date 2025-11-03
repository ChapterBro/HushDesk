from __future__ import annotations

from hushdesk.core.rules.holds import parse_strict_rules
from hushdesk.pdf.engines.mupdf_engine import MuPdfEngine
from hushdesk.pdf.grid_geometry import parameter_strips
from hushdesk.pdf.layout import extract_rows


def test_parameter_strips_capture_sbp(parameter_rules_pdf):
    engine = MuPdfEngine()
    pdf_path = str(parameter_rules_pdf)
    words = list(engine.extract_words(pdf_path))
    assert words, "Expected synthetic PDF to yield words"

    # Populate geometry caches
    extract_rows(words, source_path=pdf_path)

    strips = parameter_strips(pdf_path, page_index=0)
    strip_texts = [strip.text for strip in strips if "SBP" in strip.text.upper()]
    assert len(strip_texts) >= 2

    normalized = [" ".join(line.strip() for line in text.splitlines() if line.strip()) for text in strip_texts]
    rules = parse_strict_rules("\n".join(normalized))
    assert any(r.metric == "SBP" and r.op == "<" and r.threshold == 90 for r in rules)
    assert any(r.metric == "SBP" and r.op == ">" and r.threshold == 160 for r in rules)
