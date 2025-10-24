from __future__ import annotations
from typing import List, Tuple

from hushdesk.core.pdf.reader import page_text_spans, vertical_lines_x

Band = Tuple[float, float]
XBand = Tuple[float, float]

def detect_day_columns(doc, page_index: int) -> List[XBand]:
    """
    Build day column x-bands:
      1) Header numerals (1..31) → provisional bands around their span boxes.
      2) Extract vertical line x-positions; if two lines bracket a numeral center,
         snap band edges to those lines (±20px window).
      3) De-duplicate bands closer than 10px.
    """
    spans = page_text_spans(doc, page_index)
    days = [s for s in spans if (txt := s["text"].strip()).isdigit() and 1 <= int(txt) <= 31]
    days.sort(key=lambda s: s["bbox"][0])

    # Provisional bands from numerals (wider padding for messy headers)
    bands: List[XBand] = []
    centers: List[float] = []
    for s in days:
        x0 = s["bbox"][0] - 14
        x1 = s["bbox"][2] + 14
        bands.append((x0, x1))
        centers.append((s["bbox"][0] + s["bbox"][2]) / 2.0)

    # Snap to vertical lines if available
    vxs = vertical_lines_x(doc, page_index, min_len=120.0, x_jitter=1.5)
    if vxs and centers:
        snapped: List[XBand] = []
        for (x0, x1), xc in zip(bands, centers):
            # find nearest left/right grid lines around numeral center within ±20px
            lefts = [x for x in vxs if x <= xc + 1e-6]
            rights = [x for x in vxs if x >= xc - 1e-6]
            lx = max(lefts) if lefts else x0
            rx = min(rights) if rights else x1
            if abs(lx - xc) <= 20 and abs(rx - xc) <= 20 and rx > lx + 4:
                snapped.append((lx, rx))
            else:
                snapped.append((x0, x1))
        bands = snapped

    # De-dup near-equal bands
    bands.sort(key=lambda b: b[0])
    merged: List[List[float]] = []
    for x0, x1 in bands:
        if not merged:
            merged.append([x0, x1])
            continue
        prev = merged[-1]
        if x0 <= prev[1] + 6:
            prev[1] = max(prev[1], x1)
        elif abs(x0 - prev[0]) <= 6:
            prev[0] = min(prev[0], x0)
            prev[1] = max(prev[1], x1)
        else:
            merged.append([x0, x1])
    clean: List[XBand] = [(a, b) for a, b in merged]
    return clean

def cell_bbox(block, track_band: Band, day_band: XBand) -> Tuple[float,float,float,float]:
    x0, x1 = day_band
    y0, y1 = track_band
    bx0, by0, bx1, by1 = block.bbox
    # grid starts to the right of the block
    return (max(x0, bx1), y0, x1, y1)

def nearest_day_band(day_bands: List[XBand], x_center: float):
    if not day_bands:
        return None
    for band in day_bands:
        if band[0] <= x_center <= band[1]:
            return band
    return min(day_bands, key=lambda b: abs(((b[0] + b[1]) / 2.0) - x_center))
