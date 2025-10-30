import pytest

from hushdesk.pdf.timeparse import normalize_time_token


@pytest.mark.parametrize(
    "token, expected",
    [
        ("0600", {"normalized_time": "06:00", "time_range": None, "slot": None}),
        ("6a-10", {"normalized_time": None, "time_range": "06:00-10:00", "slot": "am"}),
        ("PM", {"normalized_time": None, "time_range": None, "slot": "pm"}),
        ("HS", {"normalized_time": None, "time_range": None, "slot": "hs"}),
        ("8pm-1", {"normalized_time": None, "time_range": "20:00-01:00", "slot": "overnight"}),
        ("11a -", {"normalized_time": None, "time_range": "11:00-13:59", "slot": "noon"}),
        ("12p-2", {"normalized_time": None, "time_range": "12:00-14:00", "slot": "noon"}),
        ("2100", {"normalized_time": "21:00", "time_range": None, "slot": None}),
    ],
)
def test_normalize_time_tokens_expected_values(token, expected):
    norm = normalize_time_token(token)
    assert norm.raw_time == token.strip()
    assert norm.normalized_time == expected["normalized_time"]
    assert norm.time_range == expected["time_range"]
    assert norm.slot == expected["slot"]
