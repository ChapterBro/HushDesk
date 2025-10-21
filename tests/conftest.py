from __future__ import annotations

from datetime import datetime
from io import BytesIO
from pathlib import Path
import sys
from typing import List, Tuple

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from hushdesk.core.timeutil import CT


class SimplePDFBuilder:
    def __init__(self) -> None:
        self.pages: List[List[Tuple[float, float, str]]] = []

    @staticmethod
    def _escape(text: str) -> str:
        return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

    def add_page(self) -> List[Tuple[float, float, str]]:
        page: List[Tuple[float, float, str]] = []
        self.pages.append(page)
        return page

    def write(self, path: Path) -> None:
        total_pages = len(self.pages)
        total_objects = 3 + total_pages * 2
        data = [""] * (total_objects + 1)
        data[1] = "<< /Type /Catalog /Pages 2 0 R >>"
        page_refs = " ".join(f"{5 + i * 2} 0 R" for i in range(total_pages))
        data[2] = f"<< /Type /Pages /Kids [{page_refs}] /Count {total_pages} >>"
        data[3] = "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"

        for index, entries in enumerate(self.pages):
            lines = ["BT"]
            for x, y, text in entries:
                escaped = self._escape(text)
                lines.append(f"/F1 12 Tf 1 0 0 1 {x:.2f} {y:.2f} Tm ({escaped}) Tj")
            lines.append("ET")
            content = "\n".join(lines) + "\n"
            content_obj = 4 + index * 2
            page_obj = 5 + index * 2
            data[content_obj] = (
                f"<< /Length {len(content.encode('utf-8'))} >>\nstream\n{content}endstream"
            )
            data[page_obj] = (
                f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents {content_obj} 0 R "
                f"/Resources << /Font << /F1 3 0 R >> >> >>"
            )

        buffer = BytesIO()
        buffer.write(b"%PDF-1.4\n")
        offsets = [0] * (total_objects + 1)
        for obj_num in range(1, total_objects + 1):
            offsets[obj_num] = buffer.tell()
            buffer.write(f"{obj_num} 0 obj\n".encode("utf-8"))
            buffer.write(data[obj_num].encode("utf-8"))
            buffer.write("\nendobj\n".encode('utf-8'))
        xref_pos = buffer.tell()
        buffer.write(f"xref\n0 {total_objects + 1}\n".encode("utf-8"))
        buffer.write(b"0000000000 65535 f \n")
        for obj_num in range(1, total_objects + 1):
            buffer.write(f"{offsets[obj_num]:010d} 00000 n \n".encode("utf-8"))
        buffer.write(
            (
                "trailer\n"
                f"<< /Size {total_objects + 1} /Root 1 0 R >>\n"
                "startxref\n"
                f"{xref_pos}\n"
                "%%EOF"
            ).encode("utf-8")
        )
        path.write_bytes(buffer.getvalue())


def _compose_page(builder: SimplePDFBuilder, data: dict, day: int) -> None:
    page = builder.add_page()
    days = data.get("days") or [day - 1, day, day + 1]
    base_x = 300
    for idx, day_num in enumerate(days):
        page.append((base_x + idx * 30, 720, str(day_num)))
    y = 620
    for row in data["rows"]:
        page.append((60, y, row["rule_text"]))
        column_x = 330 + (row.get("day_offset", 0) * 30)
        if row.get("tick"):
            page.append((column_x, y, "✓"))
        elif row.get("hold"):
            page.append((column_x, y, "Hold"))
        page.append((column_x + 30, y, row["time"]))
        y -= 24
    vitals_y = 400
    for row in data["rows"]:
        for line in row.get("vitals", []):
            page.append((60, vitals_y, line))
            vitals_y -= 16
    room = data.get("room") or data["rows"][0].get("room", "")
    if room:
        page.append((480, 80, room))


@pytest.fixture
def make_pdf(tmp_path: Path):
    def factory(name: str, *, day: int = 5, pages: list[dict]) -> Path:
        builder = SimplePDFBuilder()
        for page_data in pages:
            _compose_page(builder, page_data, day)
        target = tmp_path / name
        builder.write(target)
        return target

    return factory


@pytest.fixture
def audit_day() -> datetime:
    return datetime(2024, 5, 5, tzinfo=CT)
