from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Protocol


class EngineUnavailable(RuntimeError):
    """Raised when a PDF extraction engine cannot be used."""


@dataclass(frozen=True)
class Word:
    x0: float
    y0: float
    x1: float
    y1: float
    text: str
    page: int

    @property
    def height(self) -> float:
        return max(0.0, self.y1 - self.y0)

    @property
    def width(self) -> float:
        return max(0.0, self.x1 - self.x0)


@dataclass(frozen=True)
class Cell:
    text: str
    x0: float
    y0: float
    x1: float
    y1: float

    @property
    def width(self) -> float:
        return max(0.0, self.x1 - self.x0)

    @property
    def height(self) -> float:
        return max(0.0, self.y1 - self.y0)


@dataclass(frozen=True)
class Row:
    cells: list[Cell]
    y0: float
    y1: float
    page: int


class PdfEngine(Protocol):
    def extract_words(self, path: str) -> Iterable[Word]:
        ...
