from hushdesk.core.engine.decide import decide_due, CellTokens
from hushdesk.core.rules.holds import Rule

def mk(room="201-1", hall="Holaday", date="10-14-2025", track="AM", rules=None,
       due=None, bp=None):
    rules = rules or []
    due = due or CellTokens()
    return decide_due(room=room, hall=hall, date=date, track=track,
                      rules=rules, tokens_due=due, tokens_bp=bp, source={"page":1,"col":14,"track":track,"block_id":1})

def test_dcd_by_x_in_due_cell():
    recs = mk(due=CellTokens(x_mark=True))
    assert recs and recs[0].decision == "DC'D" and recs[0].reviewed

def test_held_appropriate_by_allowed_code():
    recs = mk(rules=[Rule("SBP",">",160)],
              due=CellTokens(chart_code=11),
              bp=CellTokens(sbp=170, dbp=60))
    assert recs and recs[0].decision == "HELD-APPROPRIATE"

def test_hold_miss_when_rule_triggers_and_given():
    recs = mk(rules=[Rule("SBP",">",160)],
              due=CellTokens(given=True, time="08:00"),
              bp=CellTokens(sbp=165, dbp=70))
    assert any(r.decision == "HOLD-MISS" for r in recs)

def test_compliant_when_given_and_no_trigger():
    recs = mk(rules=[Rule("SBP",">",160)],
              due=CellTokens(given=True, time="08:00"),
              bp=CellTokens(sbp=142, dbp=64))
    assert any(r.decision == "COMPLIANT" for r in recs)

def test_dcd_priority_over_rules():
    recs = mk(rules=[Rule("SBP","<",110)],
              due=CellTokens(x_mark=True, given=True, time="08:00"),
              bp=CellTokens(sbp=90, dbp=60))
    assert recs and recs[0].decision == "DC'D"
