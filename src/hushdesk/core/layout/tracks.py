from __future__ import annotations
from typing import Dict, Tuple, List
from hushdesk.core.pdf.reader import page_text_spans
from hushdesk.core.layout.blocks import Block

Band = Tuple[float, float]

def calibrate_tracks(doc, page_index: int, block: Block) -> Dict[str, Band]:
    spans = page_text_spans(doc, page_index)
    x0,y0,x1,y1 = block.bbox
    spans = [s for s in spans if y0 <= s["bbox"][1] <= y1 and x0 <= s["bbox"][0] <= x1]
    labels = {"AM":[], "PM":[], "BP":[]}
    for s in spans:
        t = s["text"].strip().upper()
        if t in labels:
            yc = (s["bbox"][1]+s["bbox"][3])/2
            labels[t].append(yc)
    bands: Dict[str,Band] = {}
    for k, ys in labels.items():
        if ys:
            yc = sum(ys)/len(ys)
            bands[k] = (yc-8, yc+8)
    return bands
