from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest

from hushdesk.core import audit, exporters
from hushdesk.core.timeutil import CT


def _run_sample(make_pdf, audit_day):
    pdf = make_pdf(
        "privacy.pdf",
        pages=[
            {
                "rows": [
                    {
                        "rule_text": "Lisinopril SBP < 110",
                        "time": "07:30",
                        "tick": True,
                        "room": "307A",
                        "vitals": ["SBP 150 @ 07:15", "HR 70 @ 07:18"],
                    }
                ]
            }
        ],
    )
    results, meta = audit.run_audit(str(pdf), audit_day)
    return results, meta


def test_export_room_only(make_pdf, tmp_path, audit_day):
    results, meta = _run_sample(make_pdf, audit_day)
    out_json = tmp_path / "out.json"
    exporters.export_json(out_json, results, meta)
    data = out_json.read_text()
    assert "med_name" not in data

    out_txt = tmp_path / "out.txt"
    exporters.export_txt(out_txt, results)
    content = out_txt.read_text()
    assert "Lisinopril" not in content


def test_export_with_names(make_pdf, tmp_path, audit_day):
    results, meta = _run_sample(make_pdf, audit_day)
    out_json = tmp_path / "out.json"
    exporters.export_json(out_json, results, meta, include_names=True)
    data = out_json.read_text()
    assert "Lisinopril" in data

    out_txt = tmp_path / "out.txt"
    exporters.export_txt(out_txt, results, include_names=True)
    content = out_txt.read_text()
    assert "Lisinopril" in content


def test_export_cancel(make_pdf, audit_day):
    results, meta = _run_sample(make_pdf, audit_day)
    with pytest.raises(exporters.ExportCancelled):
        exporters.export_json(None, results, meta)
