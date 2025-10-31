from __future__ import annotations

from pathlib import Path
from typing import Iterable, Iterator

from .._mupdf import import_fitz
from ..engine_base import EngineUnavailable, Word


class MuPdfEngine:
    def __init__(self) -> None:
        try:
            self._fitz = import_fitz()
        except Exception as exc:  # pragma: no cover - import guard
            raise EngineUnavailable("MuPDF (PyMuPDF) not available") from exc

    def extract_words(self, path: str) -> Iterable[Word]:
        doc_path = Path(path)
        if not doc_path.exists():
            raise FileNotFoundError(path)
        return self._iter_words(doc_path)

    def _iter_words(self, path: Path) -> Iterator[Word]:
        doc = self._fitz.open(path)
        try:
            for page_index, page in enumerate(doc):
                for entry in page.get_text("words"):  # type: ignore[assignment]
                    if not entry or len(entry) < 5:
                        continue
                    x0, y0, x1, y1, text = entry[:5]
                    if text is None:
                        continue
                    stripped = text.strip()
                    if not stripped:
                        continue
                    yield Word(float(x0), float(y0), float(x1), float(y1), stripped, page=page_index)
        finally:
            doc.close()
