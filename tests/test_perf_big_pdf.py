from __future__ import annotations

from hushdesk.core import audit


def test_perf_big_pdf(make_pdf, audit_day):
    pages = []
    for idx in range(160):
        hour = 6 + (idx % 6)
        pages.append(
            {
                "rows": [
                    {
                        "rule_text": "Lisinopril SBP < 150",
                        "time": f"{hour:02d}:00",
                        "tick": True,
                        "room": "307A",
                        "vitals": [
                            f"SBP 120 @ {hour:02d}:30",
                            f"HR 72 @ {hour:02d}:20",
                        ],
                    }
                ]
            }
        )
    pdf = make_pdf("perf.pdf", pages=pages)
    results, meta = audit.run_audit(str(pdf), audit_day)
    assert len(results) == 160
    assert meta["summary"]["reviewed"] == 160
    assert meta["summary"]["invariant_ok"]
