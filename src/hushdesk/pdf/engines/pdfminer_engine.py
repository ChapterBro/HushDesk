from __future__ import annotations

from pathlib import Path
from typing import Iterable, Iterator

from pdfminer.high_level import extract_pages
from pdfminer.layout import LAParams, LTAnno, LTChar, LTTextContainer, LTTextLine

from ..engine_base import EngineUnavailable, Word


class PdfMinerEngine:
    def __init__(self) -> None:
        try:
            import pdfminer  # noqa: F401
        except Exception as exc:  # pragma: no cover - import guard
            raise EngineUnavailable("pdfminer.six not available") from exc

    def extract_words(self, path: str) -> Iterable[Word]:
        doc_path = Path(path)
        if not doc_path.exists():
            raise FileNotFoundError(path)
        laparams = LAParams(char_margin=2.0, line_margin=0.5, word_margin=0.1)
        return self._iter_words(doc_path, laparams)

    def _iter_words(self, path: Path, laparams: LAParams) -> Iterator[Word]:
        for page_index, page in enumerate(extract_pages(path, laparams=laparams)):
            page_height = getattr(page, "height", None)
            if page_height is None and hasattr(page, "bbox"):
                try:
                    page_height = float(page.bbox[3])
                except Exception:
                    page_height = None
            for element in page:
                if not isinstance(element, LTTextContainer):
                    continue
                for line in element:
                    if not isinstance(line, LTTextLine):
                        continue
                    yield from self._words_from_line(line, page_index, page_height)

    def _words_from_line(self, line: LTTextLine, page_index: int, page_height: float | None) -> Iterator[Word]:
        buffer = []
        x0 = y0 = x1 = y1 = None

        def flush() -> Iterator[Word]:
            nonlocal buffer, x0, y0, x1, y1
            if buffer:
                text = "".join(buffer).strip()
                if text:
                    word_y0 = float(y0)
                    word_y1 = float(y1)
                    if page_height is not None:
                        top_y0 = float(page_height - word_y1)
                        top_y1 = float(page_height - word_y0)
                    else:
                        top_y0 = word_y0
                        top_y1 = word_y1
                    yield Word(float(x0), top_y0, float(x1), top_y1, text, page=page_index)
            buffer = []
            x0 = y0 = x1 = y1 = None

        for item in line:
            if isinstance(item, LTChar):
                char = item.get_text()
                if char.isspace():
                    yield from flush()
                    continue
                if not buffer:
                    x0, y0 = item.x0, item.y0
                    x1, y1 = item.x1, item.y1
                else:
                    x0 = min(x0, item.x0)
                    y0 = min(y0, item.y0)
                    x1 = max(x1, item.x1)
                    y1 = max(y1, item.y1)
                buffer.append(char)
            elif isinstance(item, LTAnno):
                yield from flush()
        yield from flush()
