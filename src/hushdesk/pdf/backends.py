from typing import Any


class PdfUnavailable(Exception):
    pass


class PdfBackend:
    name = "unknown"

    def open(self, path: str) -> Any:
        raise NotImplementedError


class MuPdfBackend(PdfBackend):
    name = "mupdf"

    def __init__(self):
        import fitz  # PyMuPDF

        self._fitz = fitz

    def open(self, path: str):
        return self._fitz.open(path)


class PlumberBackend(PdfBackend):
    name = "pdfplumber"

    def __init__(self):
        import pdfplumber

        self._pl = pdfplumber

    def open(self, path: str):
        return self._pl.open(path)


def get_backend() -> PdfBackend:
    try:
        return MuPdfBackend()
    except Exception:
        try:
            return PlumberBackend()
        except Exception as exc:
            raise PdfUnavailable("No PDF backend available") from exc
