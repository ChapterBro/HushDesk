from __future__ import annotations

import math
from typing import Any, Dict, List, Tuple

from hushdesk.pdf.backends import get_backend

try:  # Optional dependency
    import fitz  # type: ignore
except Exception:  # pragma: no cover - optional import
    fitz = None  # type: ignore

try:  # Optional dependency
    import pdfplumber  # type: ignore
except Exception:  # pragma: no cover - optional import
    pdfplumber = None  # type: ignore

Rect = Tuple[float, float, float, float]


class PdfDocument:
    """Thin wrapper that normalizes backend behaviour."""

    def __init__(self, raw_doc: Any, backend_name: str) -> None:
        self._raw = raw_doc
        self.backend = backend_name

    def __getattr__(self, name: str) -> Any:
        return getattr(self._raw, name)

    def __len__(self) -> int:
        if self.backend == "mupdf":
            return len(self._raw)
        if self.backend == "pdfplumber":
            return len(getattr(self._raw, "pages", []))
        return len(self._raw)

    def close(self) -> None:
        close = getattr(self._raw, "close", None)
        if callable(close):
            close()

    def load_page(self, index: int):
        if self.backend == "mupdf":
            return self._raw.load_page(index)
        if self.backend == "pdfplumber":
            return PdfPlumberPage(self._raw.pages[index])
        raise RuntimeError(f"Unsupported PDF backend: {self.backend}")


class PdfPlumberPage:
    """Adapts pdfplumber's page with the subset API we rely on."""

    def __init__(self, page: Any) -> None:
        self._page = page

    def _words(self) -> List[Dict[str, Any]]:
        return self._page.extract_words(use_text_flow=True, keep_blank_chars=False) or []

    def text_spans(self) -> List[Dict[str, Any]]:
        spans: List[Dict[str, Any]] = []
        for word in self._words():
            text = word.get("text") or ""
            if not text.strip():
                continue
            x0 = float(word.get("x0", 0.0))
            x1 = float(word.get("x1", x0))
            top = float(word.get("top", word.get("y0", 0.0)))
            bottom = float(word.get("bottom", word.get("y1", top)))
            spans.append({"text": text, "bbox": (x0, top, x1, bottom)})
        return spans

    def get_text(self, mode: str, *, clip: Rect | None = None) -> str | Dict[str, Any]:
        if mode == "dict":
            spans = self.text_spans()
            if not spans:
                return {"blocks": []}
            return {"blocks": [{"lines": [{"spans": spans}]}]}
        if mode == "text":
            if clip:
                return self._clip_text(clip)
            return self._page.extract_text() or ""
        raise NotImplementedError(f"pdfplumber backend does not support get_text mode {mode!r}")

    def get_textbox(self, rect: Rect) -> str:
        return self._clip_text(rect)

    def _clip_text(self, rect: Rect) -> str:
        region = self._page.crop(rect, relative=False)
        return (region.extract_text() if region else "") or ""

    def get_drawings(self) -> List[Dict[str, Any]]:
        items = []
        for line in getattr(self._page, "lines", []):
            x0 = float(line.get("x0", 0.0))
            x1 = float(line.get("x1", x0))
            y0 = float(line.get("top", line.get("y0", 0.0)))
            y1 = float(line.get("bottom", line.get("y1", y0)))
            items.append(("l", x0, y0, x1, y1))
        return [{"items": items}] if items else []

    def search_for(self, needle: str) -> List[Rect]:
        rects: List[Rect] = []
        for match in self._page.search(needle) or []:
            x0 = float(match.get("x0", 0.0))
            x1 = float(match.get("x1", x0))
            y0 = float(match.get("top", match.get("y0", 0.0)))
            y1 = float(match.get("bottom", match.get("y1", y0)))
            rects.append((x0, y0, x1, y1))
        return rects


# -------- Open / basic text --------


def open_pdf(path: str) -> PdfDocument:
    backend = get_backend()
    doc = backend.open(path)
    return PdfDocument(doc, getattr(backend, "name", "unknown"))


def page(doc, page_index: int):
    if isinstance(doc, PdfDocument):
        return doc.load_page(page_index)
    if fitz is not None and isinstance(doc, fitz.Document):  # type: ignore[attr-defined]
        return doc.load_page(page_index)
    if pdfplumber is not None and isinstance(doc, pdfplumber.pdf.PDF):  # type: ignore[attr-defined]
        return PdfPlumberPage(doc.pages[page_index])
    return doc.load_page(page_index)


def page_text_spans(doc, page_index: int) -> List[Dict]:
    p = page(doc, page_index)
    if isinstance(p, PdfPlumberPage):
        return p.text_spans()
    blocks = p.get_text("dict")["blocks"]
    spans: List[Dict] = []
    for block in blocks:
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                spans.append({"text": span["text"], "bbox": tuple(span["bbox"])})
    return spans


def page_graphics(doc, page_index: int):
    return page(doc, page_index).get_drawings()


def clip_text(doc, page_index: int, rect: Rect) -> str:
    p = page(doc, page_index)
    if isinstance(p, PdfPlumberPage):
        return p.get_textbox(rect)
    if fitz is None:
        raise RuntimeError("clip_text requires PyMuPDF when pdfplumber is unavailable")
    return p.get_textbox(fitz.Rect(*rect))


def page_search(doc, page_index: int, needle: str) -> List[Rect]:
    p = page(doc, page_index)
    if isinstance(p, PdfPlumberPage):
        return p.search_for(needle)
    return [tuple(r) for r in p.search_for(needle)]


def search_rects(doc, page_index: int, needle: str) -> List[Rect]:
    return page_search(doc, page_index, needle)


def page_text_in_rect(doc, page_index: int, rect: Rect) -> str:
    p = page(doc, page_index)
    if isinstance(p, PdfPlumberPage):
        return p.get_text("text", clip=rect)
    if fitz is None:
        raise RuntimeError("page_text_in_rect requires PyMuPDF when pdfplumber is unavailable")
    return p.get_text("text", clip=fitz.Rect(*rect))


# -------- Vector graphics utilities --------


def _page_drawings(doc, page_index: int):
    return page(doc, page_index).get_drawings()


def _collect_line_segments(doc, page_index: int) -> List[Tuple[float, float, float, float]]:
    """
    Return all straight line segments (x0,y0,x1,y1) on the page.
    """
    segments: List[Tuple[float, float, float, float]] = []
    for drawing in _page_drawings(doc, page_index):
        for item in drawing.get("items", []):
            if not item:
                continue
            tag = item[0]
            if tag != "l":
                continue
            if len(item) == 5:
                _, x0, y0, x1, y1 = item
            elif len(item) == 3:
                _, p0, p1 = item
                def _coords(pt):
                    if hasattr(pt, "x") and hasattr(pt, "y"):
                        return float(pt.x), float(pt.y)
                    if isinstance(pt, (tuple, list)) and len(pt) >= 2:
                        return float(pt[0]), float(pt[1])
                    raise TypeError("Unsupported point type in drawing segment")
                x0, y0 = _coords(p0)
                x1, y1 = _coords(p1)
            else:
                continue
            segments.append((x0, y0, x1, y1))
    return segments


def vertical_lines_x(
    doc,
    page_index: int,
    *,
    min_len: float = 120.0,
    x_jitter: float = 1.5,
) -> List[float]:
    """
    Heuristically extract x-positions of vertical grid lines:
    - segment length >= min_len
    - |x0 - x1| small (near vertical)
    Cluster near-equal x into a single representative value.
    """
    segs = _collect_line_segments(doc, page_index)
    xs: List[float] = []
    for x0, y0, x1, y1 in segs:
        dx, dy = abs(x1 - x0), abs(y1 - y0)
        if dy >= min_len and dx <= 2.0:  # near-perfect vertical
            xs.append((x0 + x1) / 2.0)

    xs.sort()
    # cluster by x_jitter
    clustered: List[float] = []
    for x in xs:
        if not clustered or abs(x - clustered[-1]) > x_jitter:
            clustered.append(x)
        else:
            # average into last cluster
            clustered[-1] = (clustered[-1] + x) / 2.0
    return clustered


def has_vector_x(
    doc,
    page_index: int,
    rect: Rect,
    *,
    tol_angle: Tuple[float, float] = (35.0, 55.0),
    min_frac: float = 0.45,
    max_frac: float = 1.7,
) -> bool:
    """
    Detect an X mark drawn as two diagonals inside `rect`.
    Heuristic:
      - Two lines whose midpoints are inside rect.
      - Angles ~ 45° and ~ 135° (within tol_angle).
      - Lengths within a reasonable ratio (min_frac..max_frac).
      - The two segments cross (bounding boxes intersect and implied intersection inside rect).
    """
    x0, y0, x1, y1 = rect
    cx0, cy0, cx1, cy1 = x0, y0, x1, y1

    def inside(mid_x: float, mid_y: float) -> bool:
        return cx0 <= mid_x <= cx1 and cy0 <= mid_y <= cy1

    def angle_deg(x0: float, y0: float, x1: float, y1: float) -> float:
        return abs(math.degrees(math.atan2(y1 - y0, x1 - x0))) % 180.0

    segments = _collect_line_segments(doc, page_index)
    candidates = []
    for seg in segments:
        ax0, ay0, ax1, ay1 = seg
        mx, my = (ax0 + ax1) / 2.0, (ay0 + ay1) / 2.0
        if not inside(mx, my):
            continue
        ang = angle_deg(ax0, ay0, ax1, ay1)
        ang = min(ang, 180.0 - ang)
        if tol_angle[0] <= ang <= tol_angle[1]:
            length = math.hypot(ax1 - ax0, ay1 - ay0)
            candidates.append((seg, ang, length))

    # Look for two candidates forming an X (roughly orthogonal with similar length)
    for i in range(len(candidates)):
        for j in range(i + 1, len(candidates)):
            (_, _ai, li) = candidates[i]
            (_, _aj, lj) = candidates[j]
            ratio = li / max(lj, 1e-6)
            if min_frac <= ratio <= max_frac:
                xi0, yi0, xi1, yi1 = candidates[i][0]
                xj0, yj0, xj1, yj1 = candidates[j][0]
                box_i = (min(xi0, xi1), min(yi0, yi1), max(xi0, xi1), max(yi0, yi1))
                box_j = (min(xj0, xj1), min(yj0, yj1), max(xj0, xj1), max(yj0, yj1))
                if not (
                    box_i[2] < box_j[0]
                    or box_j[2] < box_i[0]
                    or box_i[3] < box_j[1]
                    or box_j[3] < box_i[1]
                ):
                    # Overlapping bounding boxes inside rect - treat as X
                    return True
    return False

