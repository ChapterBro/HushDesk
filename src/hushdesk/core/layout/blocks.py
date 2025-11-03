from __future__ import annotations
from dataclasses import dataclass
from typing import List, Dict, Tuple
from hushdesk.core.pdf.reader import page_text_spans, Rect

_KEYWORDS = ("SBP", "HR", "PULSE")
_CONTINUATION_HINTS = ("LESS", "GREATER", "<", ">", "THAN", "IF", "WHEN", "NOTIFY", "ABOVE", "BELOW", "WITH", "FOR", "HOLD")

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
    left_boundary = x_mid + 96
    left_spans = [s for s in spans if s["bbox"][0] < left_boundary]
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
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        rule_lines: List[str] = []
        i = 0
        while i < len(lines):
            line = lines[i]
            upper = line.upper()
            if any(key in upper for key in _KEYWORDS):
                chunk = [line]
                j = i + 1
                digits_seen = False
                steps = 0
                while j < len(lines) and steps < 8:
                    nxt = lines[j]
                    nxt_upper = nxt.upper()
                    if any(key in nxt_upper for key in _KEYWORDS):
                        break
                    if any(ch.isdigit() for ch in nxt):
                        chunk.append(nxt)
                        digits_seen = True
                        j += 1
                        steps += 1
                        continue
                    if any(hint in nxt_upper for hint in _CONTINUATION_HINTS) or not digits_seen:
                        chunk.append(nxt)
                        j += 1
                        steps += 1
                        continue
                    break
                rule_lines.append(" ".join(chunk))
                i = j
                continue
            i += 1
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
    return (max(0.0, x0 - pad), y0 - pad, x1 + pad, y1 + pad)
