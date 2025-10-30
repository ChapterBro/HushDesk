from pathlib import Path

import pytest

from hushdesk.pdf.mar_parser import ParseResult, parse_mar_pdf


def test_mar_parser_smoke() -> None:
    sample_path = Path("tests") / "data" / "sample_mar.pdf"
    if not sample_path.exists():
        pytest.xfail("MAR sample PDF not available")

    result = parse_mar_pdf(str(sample_path))
    assert isinstance(result, ParseResult)

    forbidden_keys = {"name", "dob", "room", "admit"}
    for key in result.meta.keys():
        assert key.lower() not in forbidden_keys

    assert result.doses or result.notes

    for dose in result.doses:
        assert dose.med
        assert dose.raw_time
        assert dose.cell is not None
