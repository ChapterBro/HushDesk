from __future__ import annotations
import math
from typing import List, Dict, Tuple

import fitz  # PyMuPDF

Rect = Tuple[float, float, float, float]

# -------- Open / basic text --------

def open_pdf(path: str):
    return fitz.open(path)

def page(doc, page_index: int):
    return doc.load_page(page_index)

def page_text_spans(doc, page_index: int) -> List[Dict]:
    p = page(doc, page_index)
    blocks = p.get_text("dict")["blocks"]
    spans: List[Dict] = []
    for b in blocks:
        for l in b.get("lines", []):
            for s in l.get("spans", []):
                spans.append({"text": s["text"], "bbox": tuple(s["bbox"])})
    return spans

def page_graphics(doc, page_index: int):
    return page(doc, page_index).get_drawings()

def clip_text(doc, page_index: int, rect: Rect) -> str:
    return page(doc, page_index).get_textbox(rect)

def page_search(doc, page_index: int, needle: str) -> List[Rect]:
    return [tuple(r) for r in page(doc, page_index).search_for(needle)]

def search_rects(doc, page_index: int, needle: str) -> List[Rect]:
    return page_search(doc, page_index, needle)

def page_text_in_rect(doc, page_index: int, rect: Rect) -> str:
    p = doc.load_page(page_index)
    # Use PyMuPDF clip to confine text; keep line breaks for tokenizer heuristics
    return p.get_text("text", clip=fitz.Rect(*rect))

# -------- Vector graphics utilities --------

def _page_drawings(doc, page_index: int):
    return page(doc, page_index).get_drawings()

def _collect_line_segments(doc, page_index: int) -> List[Tuple[float,float,float,float]]:
    """
    Return all straight line segments (x0,y0,x1,y1) on the page.
    """
    segs: List[Tuple[float,float,float,float]] = []
    for d in _page_drawings(doc, page_index):
        for it in d.get("items", []):
            if not it or it[0] != "l":  # only straight lines
                continue
            _, x0, y0, x1, y1 = it
            segs.append((x0, y0, x1, y1))
    return segs

def vertical_lines_x(doc, page_index: int, *, min_len: float = 120.0, x_jitter: float = 1.5) -> List[float]:
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

def has_vector_x(doc, page_index: int, rect: Rect, *, tol_angle: Tuple[float,float]=(35.0,55.0),
                 min_frac: float = 0.45, max_frac: float = 1.7) -> bool:
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

    segs = _collect_line_segments(doc, page_index)
    cands = []
    for a in segs:
        ax0, ay0, ax1, ay1 = a
        mx, my = (ax0 + ax1) / 2.0, (ay0 + ay1) / 2.0
        if not inside(mx, my):
            continue
        ang = angle_deg(ax0, ay0, ax1, ay1)
        # Normalize angle to [0,90] by folding
        ang = min(ang, 180.0 - ang)
        if tol_angle[0] <= ang <= tol_angle[1]:
            length = math.hypot(ax1 - ax0, ay1 - ay0)
            cands.append((a, ang, length))

    # Look for two candidates forming an X (roughly orthogonal with similar length)
    for i in range(len(cands)):
        for j in range(i + 1, len(cands)):
            (_, ai, li) = cands[i]
            (_, aj, lj) = cands[j]
            r = li / max(lj, 1e-6)
            if min_frac <= r <= max_frac:
                # bounding box overlap hint (cheap cross check)
                xi0, yi0, xi1, yi1 = cands[i][0]
                xj0, yj0, xj1, yj1 = cands[j][0]
                box_i = (min(xi0, xi1), min(yi0, yi1), max(xi0, xi1), max(yi0, yi1))
                box_j = (min(xj0, xj1), min(yj0, yj1), max(xj0, xj1), max(yj0, yj1))
                if not (box_i[2] < box_j[0] or box_j[2] < box_i[0] or
                        box_i[3] < box_j[1] or box_j[3] < box_i[1]):
                    # Overlapping bounding boxes inside rect → treat as X
                    return True
    return False
