"""Drag and drop helpers (placeholder for future platforms)."""
from __future__ import annotations


class DropTarget:
    def __init__(self) -> None:
        self.enabled = False

    def enable(self) -> None:
        self.enabled = True

    def disable(self) -> None:
        self.enabled = False
