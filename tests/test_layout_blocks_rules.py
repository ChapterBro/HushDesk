from __future__ import annotations

import pytest

from hushdesk.core import building_master as BM
from hushdesk.core.pdf.reader import open_pdf
from hushdesk.core.layout import blocks as layout_blocks
from hushdesk.ui import app as ui_app


@pytest.mark.usefixtures("parameter_rules_pdf")
def test_multiline_rules_rebuild(parameter_rules_pdf):
    pdf_path = str(parameter_rules_pdf)
    doc = open_pdf(pdf_path)
    try:
        blocks = layout_blocks.detect_blocks(doc, 0)
        rebuilt = [
            ui_app._rebuild_rule_text(doc, 0, block)  # type: ignore[attr-defined]
            for block in blocks
        ]
    finally:
        doc.close()

    combined = "\n".join(filter(None, rebuilt))
    assert "Hold for SBP less than 90" in combined
    assert "Hold for SBP greater than 160" in combined


def test_estimator_counts_parameter_rules(parameter_rules_pdf):
    pdf_path = str(parameter_rules_pdf)
    # Use a wide band to capture the synthetic page.
    preview = ui_app._estimate_parametered_slots(pdf_path, {0: (0.0, 612.0)})  # type: ignore[attr-defined]
    assert preview.sbp_total >= 2
    assert len(preview.highlights) == 2
    assert any("SBP < 90" in text for text in preview.highlights)
    assert any("SBP > 160" in text for text in preview.highlights)


def test_estimator_uses_geometry_rooms(parameter_rules_pdf):
    pdf_path = str(parameter_rules_pdf)
    mercer_rooms = BM.rooms_in_hall("Mercer")
    preview = ui_app._estimate_parametered_slots(  # type: ignore[attr-defined]
        pdf_path, {0: (0.0, 612.0)}, mercer_rooms
    )
    assert any(line.startswith("Room 101-1") for line in preview.highlights)
    assert not any("Room 90" in line for line in preview.highlights)


def test_estimator_drops_rooms_when_invalid_for_hall(parameter_rules_pdf):
    pdf_path = str(parameter_rules_pdf)
    morton_rooms = BM.rooms_in_hall("Morton")
    preview = ui_app._estimate_parametered_slots(  # type: ignore[attr-defined]
        pdf_path, {0: (0.0, 612.0)}, morton_rooms
    )
    assert all(not line.startswith("Room ") for line in preview.highlights)
