import re
from typing import List

_CHECKS = {"√", "✔", "✓"}
_JOIN_PAIRS = {("√", "bakk"), ("√", "siba"), ("√", "jn1"), ("√", "bail")}
_HOLD = {"H", "hold", "Hold"}


def join_tokens(tokens: List[str]) -> str:
    toks = [t.strip() for t in tokens if t and t.strip()]
    out: List[str] = []
    i = 0
    while i < len(toks):
        cur = toks[i]
        nxt = toks[i + 1] if i + 1 < len(toks) else None
        # join known check+initials
        if nxt and (cur, nxt) in _JOIN_PAIRS:
            out.append(cur + nxt)  # "√" + "bakk" -> "√bakk"
            i += 2
            continue
        if cur in _CHECKS:
            out.append("√")
        elif cur in _HOLD:
            out.append("H")
        else:
            out.append(re.sub(r"\s+", " ", cur))
        i += 1
    return " ".join(out).strip()

