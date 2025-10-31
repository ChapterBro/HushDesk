from __future__ import annotations

from pathlib import Path
from typing import List

from ._mupdf import import_fitz


def extract_text_by_page(path: str) -> List[List[str]]:
    """
    Return the textual contents of each PDF page as a list of line lists.

    The loader walks through a set of available backends (PyMuPDF, pdfplumber,
    pdfminer.six) and uses the first one that succeeds. This keeps the legacy
    MAR parser working in environments where the optional compiled module
    previously providing ``pdfio`` is unavailable.
    """

    pdf_path = Path(path)
    if not pdf_path.exists():
        raise FileNotFoundError(str(pdf_path))

    errors: List[str] = []

    for extractor in (_extract_with_pymupdf, _extract_with_pdfplumber, _extract_with_pdfminer):
        try:
            pages = extractor(str(pdf_path))
            if pages is not None:
                return pages
        except ModuleNotFoundError:
            continue
        except ImportError:
            continue
        except Exception as exc:
            errors.append(f"{extractor.__name__}: {exc}")
            continue

    error_detail = "; ".join(errors) if errors else "no PDF backend available"
    raise RuntimeError(f"pdfio.extract_text_by_page not available ({error_detail})")


def _normalize_lines(text: str) -> List[str]:
    lines: List[str] = []
    for raw in text.splitlines():
        cleaned = raw.strip()
        if cleaned:
            lines.append(cleaned)
    return lines


def _extract_with_pymupdf(path: str) -> List[List[str]] | None:
    fitz = import_fitz(optional=True)
    if fitz is None:
        raise ModuleNotFoundError("fitz")

    doc = fitz.open(path)  # type: ignore[attr-defined]
    try:
        pages: List[List[str]] = []
        for page in doc:
            text = page.get_text("text") or ""
            pages.append(_normalize_lines(text))
        return pages
    finally:
        doc.close()


def _extract_with_pdfplumber(path: str) -> List[List[str]] | None:
    try:
        import pdfplumber
    except Exception as exc:
        raise ModuleNotFoundError("pdfplumber") from exc

    with pdfplumber.open(path) as pdf:
        pages: List[List[str]] = []
        for page in pdf.pages:
            text = page.extract_text() or ""
            pages.append(_normalize_lines(text))
        return pages


def _extract_with_pdfminer(path: str) -> List[List[str]] | None:
    try:
        from pdfminer.high_level import extract_pages
        from pdfminer.layout import LAParams, LTTextContainer, LTTextLine
    except Exception as exc:
        raise ModuleNotFoundError("pdfminer") from exc

    laparams = LAParams(char_margin=2.0, line_margin=0.5, word_margin=0.1)
    pages: List[List[str]] = []
    for page_layout in extract_pages(path, laparams=laparams):
        lines: List[str] = []
        for element in page_layout:
            if not isinstance(element, LTTextContainer):
                continue
            for text_line in element:
                if not isinstance(text_line, LTTextLine):
                    continue
                line_text = text_line.get_text().strip()
                if line_text:
                    lines.append(line_text)
        pages.append(lines)
    return pages
