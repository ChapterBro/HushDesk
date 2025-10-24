from __future__ import annotations
from dataclasses import dataclass
from typing import List, Dict, Tuple
from hushdesk.core.pdf.reader import page_text_spans, Rect

@dataclass
class Block:
    id: int
    bbox: Rect
    left_text: str
    rule_text: str

def detect_blocks(doc, page_index: int) -> List[Block]:
    spans = page_text_spans(doc, page_index)
    if not spans: return []
    xs = [s["bbox"][0] for s in spans]
    x_mid = sorted(xs)[len(xs)//2]
    left_spans = [s for s in spans if s["bbox"][0] < x_mid]
    left_spans.sort(key=lambda s: (s["bbox"][1], s["bbox"][0]))

    blocks: List[Block] = []
    cur: List[Dict] = []; last_y = None
    def flush():
        nonlocal blocks, cur
        if not cur: return
        y0 = min(s["bbox"][1] for s in cur) - 2
        y1 = max(s["bbox"][3] for s in cur) + 2
        x0 = min(s["bbox"][0] for s in cur) - 2
        x1 = max(s["bbox"][2] for s in cur) + 2
        text = "\n".join(s["text"] for s in cur)
        rule_lines = [ln for ln in text.splitlines() if any(k in ln.upper() for k in ("SBP","HR","PULSE"))]
        blocks.append(Block(id=len(blocks), bbox=(x0,y0,x1,y1), left_text=text, rule_text="\n".join(rule_lines)))
        cur = []
    for s in left_spans:
        y = s["bbox"][1]
        if last_y is None or abs(y - last_y) < 12:
            cur.append(s)
        else:
            flush(); cur = [s]
        last_y = y
    flush()
    return blocks

def block_left_strip(block: Block, pad: float = 6.0):
    x0, y0, x1, y1 = block.bbox
    return (x0, y0, min(x1, x0 + 0.25 * (x1 - x0)) + pad, y1)
