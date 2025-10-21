from __future__ import annotations

from datetime import datetime

from hushdesk.core.timeutil import CT, default_audit_day


def test_default_audit_day_regular():
    ref = datetime(2024, 5, 5, 12, 0, tzinfo=CT)
    assert default_audit_day(ref).isoformat() == "2024-05-04"


def test_default_audit_day_dst_fall_back():
    ref = datetime(2024, 11, 3, 1, 30, tzinfo=CT)
    assert default_audit_day(ref).isoformat() == "2024-11-02"
