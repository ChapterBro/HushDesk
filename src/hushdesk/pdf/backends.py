from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol


class PdfUnavailable(RuntimeError):
    """Raised when no working PDF backend is importable."""


class PdfBackend(Protocol):
    name: str

    def open(self, path: str) -> Any:
        ...


@dataclass
class MuPdfBackend:
    name: str = "mupdf"

    def __post_init__(self) -> None:
        import fitz  # PyMuPDF

        self._fitz = fitz

    def open(self, path: str) -> Any:
        return self._fitz.open(path)


@dataclass
class PlumberBackend:
    name: str = "pdfplumber"

    def __post_init__(self) -> None:
        import pdfplumber

        self._plumber = pdfplumber

    def open(self, path: str) -> Any:
        return self._plumber.open(path)


def get_backend() -> PdfBackend:
    """Prefer MuPDF; fallback to pdfplumber; error if neither can import."""
    try:
        return MuPdfBackend()
    except Exception:
        try:
            return PlumberBackend()
        except Exception as exc:
            raise PdfUnavailable("no_pdf_backend") from exc

