from __future__ import annotations

from hushdesk.core import audit


def test_summary_invariant(make_pdf, audit_day):
    pdf = make_pdf(
        "invariant.pdf",
        pages=[
            {
                "rows": [
                    {
                        "rule_text": "Metoprolol SBP < 140",
                        "time": "08:00",
                        "tick": True,
                        "room": "307A",
                        "vitals": ["SBP 130 @ 07:40", "HR 70 @ 07:45"],
                    },
                    {
                        "rule_text": "Losartan SBP < 110",
                        "time": "08:30",
                        "hold": True,
                        "room": "307A",
                        "vitals": ["SBP 150 @ 09:00", "HR 82 @ 08:45"],
                    },
                    {
                        "rule_text": "Hydralazine SBP <= 120",
                        "time": "09:00",
                        "tick": True,
                        "room": "307A",
                        "vitals": ["SBP 118 @ 09:10", "HR 74 @ 09:12"],
                    },
                ]
            }
        ],
    )
    results, meta = audit.run_audit(str(pdf), audit_day)
    summary = meta["summary"]
    assert summary["reviewed"] == len(results)
    assert summary["reviewed"] == summary["held"] + summary["compliant"] + summary["exceptions"]
    assert summary["held"] == 1
    assert summary["compliant"] == 1
    assert summary["exceptions"] == 1
