from __future__ import annotations
from hushdesk.mar import parser as mar_parser

def test_parse_matches_fixture_payload(synthetic_mar_pdf, synthetic_fixture_payload):
    result = mar_parser.parse_mar(str(synthetic_mar_pdf))
    assert result.fixture_payload == synthetic_fixture_payload
