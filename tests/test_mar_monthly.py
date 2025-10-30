from __future__ import annotations

from hushdesk.ui import app


def test_day_column_resolver_detects_day_band(monthly_mar_pdf):
    resolver = app.DayColumnResolver.build(str(monthly_mar_pdf))
    bands = resolver.bands_for_day(30)
    assert bands, "Expected day bands for target day"
    for band in bands.values():
        assert band[1] > band[0]


def test_detect_hall_from_pdf_header_focus(monthly_mar_pdf):
    detection = app._detect_hall_from_pdf(str(monthly_mar_pdf))
    assert detection.hall == "Bridgeman"
    assert detection.score >= 1
    assert "Bridgeman" in detection.candidates


def test_build_preview_decisions_monthly_grid(monthly_mar_pdf):
    resolver = app.DayColumnResolver.build(str(monthly_mar_pdf))
    day_bands = resolver.bands_for_day(30)
    decisions, header_meta = app._build_preview_decisions(
        pdf_path=str(monthly_mar_pdf),
        hall="Bridgeman",
        date_str="10-30-2025",
        rooms=["307-2"],
        day_bands=day_bands,
        page_count=resolver.pages,
    )
    assert decisions
    assert header_meta["pages"] == resolver.pages
    assert any(dec.decision == "HOLD-MISS" for dec in decisions)


def test_run_pdf_backend_preview_summary(monthly_mar_pdf):
    payload = app.run_pdf_backend(str(monthly_mar_pdf), date_str="10-30-2025", room_filter="307-2")
    assert payload["ok"] is True
    summary = payload["summary"]
    assert summary["reviewed"] > 0
    assert summary["hold_miss"] > 0
    hold_section = payload["sections"].get("HOLD-MISS", [])
    assert hold_section, "Expected HOLD-MISS section populated"
