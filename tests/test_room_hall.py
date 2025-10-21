from __future__ import annotations

from __future__ import annotations

from hushdesk.core import audit
from hushdesk.core import building_master as bm


def test_room_normalization_and_validation():
    assert bm.normalize_room("307A") == "307-1"
    assert bm.normalize_room("307B") == "307-2"
    assert bm.normalize_room("307") == "307-1"
    assert not bm.normalize_room("120/80")
    assert bm.is_valid_room("307-1")
    assert not bm.is_valid_room("999-1")
    assert bm.prefix_for_room(307) == "300s"


def test_hall_detection_mode(make_pdf, audit_day):
    pdf = make_pdf(
        "hall.pdf",
        pages=[
            {
                "rows": [
                    {
                        "rule_text": "Amlodipine SBP < 140",
                        "time": "07:00",
                        "tick": True,
                        "room": "307A",
                        "vitals": ["SBP 130 @ 06:40", "HR 72 @ 06:45"],
                    }
                ]
            },
            {
                "rows": [
                    {
                        "rule_text": "Amlodipine SBP < 140",
                        "time": "19:00",
                        "tick": True,
                        "room": "307B",
                        "vitals": ["SBP 134 @ 18:40", "HR 70 @ 18:45"],
                    }
                ]
            },
        ],
    )
    _, meta = audit.run_audit(str(pdf), audit_day)
    assert meta["hall_name"] == "Bridgman"
    assert meta["hall_short"] == "Bridgman"
