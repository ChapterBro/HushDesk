from __future__ import annotations
import os
from pathlib import Path
from typing import Dict, List
from hushdesk.core.privacy_runtime import ensure_private_dir, secure_open_for_write
from hushdesk.version import APP_VERSION

# try to import scrubber (no-op fallback if unavailable)
try:
    from hushdesk.core.privacy_guard import sanitize_line as _scrub
except Exception:
    _scrub = None

def _sanitize(s: str) -> str:
    s = (s or "").rstrip("\r\n")
    return _scrub(s) if _scrub else s

def write_txt(path: str, header: Dict, summary: Dict, sections: Dict[str, List[str]]) -> str:
    """
    header: {"date_str":"MM-DD-YYYY","hall":"Holaday","source":"file.pdf"?}
    summary: {"reviewed":N,"hold_miss":N,"held_ok":N,"compliant":N,"dcd":N}
    sections: {"HOLD-MISS":[...],"HELD-APPROPRIATE":[...],"COMPLIANT":[...],"DC'D":[...]}
    Each line already formatted as "<room> (<AM|PM>) - ...".
    """
    lines: List[str] = []

    # Header (sanitized)
    lines.append(f"Date: {_sanitize(header.get('date_str',''))}")
    lines.append(f"Hall: {_sanitize(header.get('hall',''))}")
    src = header.get("source")
    if src:
        lines.append(f"Source: {_sanitize(src)}")
    lines.append("")

    # Summary
    lines.append(f"Reviewed: {int(summary.get('reviewed',0))}")
    lines.append(f"Hold-Miss: {int(summary.get('hold_miss',0))}")
    lines.append(f"Held-Appropriate: {int(summary.get('held_ok',0))}")
    lines.append(f"Compliant: {int(summary.get('compliant',0))}")
    lines.append(f"DC'D: {int(summary.get('dcd',0))}")
    lines.append("")

    # Sections (fixed order; sanitize each)
    for title in ("HOLD-MISS","HELD-APPROPRIATE","COMPLIANT","DC'D"):
        items = sections.get(title, []) or []
        clean = [_sanitize(x) for x in items if x and _sanitize(x)]
        if not clean:
            continue
        lines.append(title)
        lines.extend(clean)
        lines.append("")

    # Central timestamp (America/Chicago fixed offset stamp)
    from datetime import datetime, timezone, timedelta
    central = datetime.now(tz=timezone(timedelta(hours=-5))).strftime("%m-%d-%Y %H:%M")
    lines.append(f"Generated: {central} (Central) • v{APP_VERSION}")

    out = "\n".join(lines) + "\n"
    p = Path(path)
    ensure_private_dir(str(p.parent))
    fd = secure_open_for_write(str(p))
    with os.fdopen(fd, "w", encoding="utf-8", newline="\n", closefd=True) as fh:
        fh.write(out)
    return str(p)
