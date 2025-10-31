from __future__ import annotations

from types import SimpleNamespace

from hushdesk.ui import app


class _StubResolver:
    pages = 1

    def bands_for_day(self, day: int):
        return {0: (0.0, 1.0)}

    @classmethod
    def build(cls, pdf_path: str):
        return cls()


def test_preview_summary_falls_back_to_parse_counts(monkeypatch, synthetic_mar_pdf):
    monkeypatch.setattr(app, "DayColumnResolver", _StubResolver)

    def _fake_preview(**kwargs):
        header_meta = {
            "date_str": kwargs.get("date_str", ""),
            "hall": kwargs.get("hall", ""),
            "source": "synthetic.pdf",
            "pages": kwargs.get("page_count", 0),
        }
        return [], header_meta

    monkeypatch.setattr(app, "_build_preview_decisions", _fake_preview)
    monkeypatch.setattr(app, "_estimate_parametered_slots", lambda path, bands: (6, ["hold for SBP < 100"]))
    detection = SimpleNamespace(hall=None, score=0, candidates=["Mercer"])
    monkeypatch.setattr(app, "_detect_hall_from_pdf", lambda pdf_path: detection)

    payload = app.run_pdf_backend(str(synthetic_mar_pdf), date_str="10-30-2025")

    assert payload["summary"]["reviewed"] == 6
    assert any("Preview metrics estimated" in note for note in payload["notes"])
