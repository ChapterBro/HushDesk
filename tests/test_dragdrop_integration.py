from __future__ import annotations
from hushdesk.ui import dragdrop

class StubModel:
    def __init__(self) -> None:
        self.success_payload = None
        self.errors = []

    def on_parse_success(self, rows, violations, meta) -> None:
        self.success_payload = (rows, violations, meta)

    def on_parse_error(self, message: str) -> None:
        self.errors.append(message)

def test_dragdrop_parses_and_updates_model(synthetic_mar_pdf, synthetic_fixture_payload):
    model = StubModel()
    ok = dragdrop.handle_drop(str(synthetic_mar_pdf), model)
    assert ok is True
    assert model.errors == []
    assert model.success_payload is not None
    rows, violations, meta = model.success_payload
    assert rows == synthetic_fixture_payload["rows"]
    assert len(violations) == len(synthetic_fixture_payload["violations"])
    assert meta.get("pages") == synthetic_fixture_payload["meta"]["pages"]
