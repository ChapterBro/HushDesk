from hushdesk.core.export.checklist_render import write_txt

def test_write_txt_creates_basic_layout(tmp_path):
    p = tmp_path / "out.txt"
    header = {"date_str":"10-14-2025","hall":"Holaday","source":"AdminRecord_2025-10-14_Holaday.pdf"}
    summary = {"reviewed":3,"hold_miss":1,"held_ok":1,"compliant":1,"dcd":0}
    sections = {
        "HOLD-MISS": ["201-1 (AM) — Hold if SBP > 160; BP 165/70; given 08:00"],
        "HELD-APPROPRIATE": ["418-1 (AM) — Hold if SBP > 160; BP 172/66; code 11"],
        "COMPLIANT": ["203-1 (AM) — Hold if SBP > 160; BP 142/64; given 08:00"],
        "DC'D": []
    }
    write_txt(str(p), header, summary, sections)
    s = p.read_text(encoding="utf-8")
    assert "Date: 10-14-2025" in s and "Hall: Holaday" in s and "Hold-Miss: 1" in s
    assert "HOLD-MISS" in s and "HELD-APPROPRIATE" in s and "COMPLIANT" in s
