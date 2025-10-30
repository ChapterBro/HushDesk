from __future__ import annotations

import pathlib


REPLACEMENTS = {
    "\u2018": "'",
    "\u2019": "'",
    "\u201c": '"',
    "\u201d": '"',
    "\u2013": "-",
    "\u2014": "-",
    "\u00a0": " ",
    "\u2026": "...",
    "\u20ac": "EUR",
}

ZERO_WIDTH = {
    "\u200b",
    "\u200c",
    "\u200d",
    "\ufeff",
}


def sanitize_text(text: str) -> str:
    for source, target in REPLACEMENTS.items():
        text = text.replace(source, target)
    for marker in ZERO_WIDTH:
        text = text.replace(marker, "")
    if text.startswith("\ufeff"):
        text = text.lstrip("\ufeff")
    return text


def process_file(path: pathlib.Path) -> bool:
    try:
        original = path.read_text(encoding="utf-8", errors="replace")
    except UnicodeDecodeError:
        original = path.read_bytes().decode("utf-8", errors="replace")
    sanitized = sanitize_text(original)
    if sanitized != original:
        path.write_text(sanitized, encoding="utf-8", newline="")
        return True
    # Always ensure UTF-8 encoding without BOM even if text unchanged.
    path.write_text(original, encoding="utf-8", newline="")
    return False


def main() -> None:
    src_root = pathlib.Path("src")
    if not src_root.exists():
        return
    for file_path in sorted(src_root.rglob("*.py")):
        process_file(file_path)


if __name__ == "__main__":
    main()
