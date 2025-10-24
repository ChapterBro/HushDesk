from hushdesk.core.rules.holds import parse_strict_rules

def test_accept_strict_ops_only():
    r = parse_strict_rules("Hold if SBP > 160\nHold if HR < 50")
    keys = {(x.metric,x.op,x.threshold) for x in r}
    assert ("SBP",">",160) in keys
    assert ("HR","<",50) in keys

def test_reject_disallowed_phrases():
    r = parse_strict_rules("SBP ≤ 160\nPulse at or below 60\nHR = 80")
    assert r == []
