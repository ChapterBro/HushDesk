from hushdesk.core.parse.tokenizer import tokenize_cell_text

def test_bp_stitch_and_parse():
    t = tokenize_cell_text("152/\n72")
    assert t.sbp == 152 and t.dbp == 72

def test_given_by_checkmark_and_time():
    t = tokenize_cell_text("√ 08:00")
    assert t.given and t.time == "08:00"

def test_chart_code_extracted_when_not_time_or_bp():
    t = tokenize_cell_text("11")
    assert t.chart_code == 11

def test_x_mark_detected():
    t = tokenize_cell_text(" X ")
    assert t.x_mark

def test_given_checkmark_with_newline():
    t = tokenize_cell_text("√\n09:15")
    assert t.given and t.time == "09:15"
