from __future__ import annotations

from pathlib import Path
from typing import Protocol

from hushdesk.mar import parser as mar_parser


class DragDropModel(Protocol):
    def on_parse_success(self, rows, violations, meta) -> None: ...

    def on_parse_error(self, message: str) -> None: ...


def handle_drop(path: str, model: DragDropModel) -> bool:
    candidate = Path(path)
    if candidate.suffix.lower() != ".pdf":
        model.on_parse_error("Unsupported file type; drop a PDF file.")
        return False
    if not candidate.exists():
        model.on_parse_error("File not found.")
        return False

    try:
        result = mar_parser.parse_mar(str(candidate))
    except Exception as exc:  # pragma: no cover - surfaced to UI
        model.on_parse_error(str(exc))
        return False

    model.on_parse_success(
        result.fixture_payload["rows"],
        result.fixture_payload["violations"],
        result.meta,
    )
    return True
