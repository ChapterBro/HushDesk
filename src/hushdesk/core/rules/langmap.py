import re

# Map spoken phrases to canonical symbols, and Pulse -> HR.
# We keep it TIGHT: only the phrases the user wants.
_PHRASES = [
    # SBP phrases
    (re.compile(r"\bSBP\s+less\s+than\b", re.I), "SBP <"),
    (re.compile(r"\bSBP\s+greater\s+than\b", re.I), "SBP >"),
    # Pulse phrases (alias to HR)
    (re.compile(r"\bPulse\s+less\s+than\b", re.I), "HR <"),
    # (optional symmetry; safe to include even if not used)
    (re.compile(r"\bPulse\s+greater\s+than\b", re.I), "HR >"),
]


def normalize_rule_text(text: str) -> str:
    """Normalize English phrases to comparator tokens and alias Pulse->HR.
    Keeps the rest of the string intact; case-insensitive; whitespace safe."""
    if not text:
        return text
    out = text
    for pat, repl in _PHRASES:
        out = pat.sub(repl, out)
    # collapse any extra spaces like 'SBP <  90' -> 'SBP < 90'
    out = re.sub(r"\s{2,}", " ", out)
    return out
