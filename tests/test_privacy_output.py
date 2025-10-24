from hushdesk.core.export.checklist_render import write_txt

def test_txt_has_no_names_or_free_text(tmp_path):
    p = tmp_path / "out.txt"
    header = {"date_str":"10-14-2025","hall":"Holaday","source":"AdminRecord_2025-10-14_Holaday.pdf"}
    summary = {"reviewed":1,"hold_miss":1,"held_ok":0,"compliant":0,"dcd":0}
    sections = {
        "HOLD-MISS": ["201-1 (AM) — Jane Doe Hold if SBP > 160; BP 165/70; given 08:00"],
        "HELD-APPROPRIATE": [],
        "COMPLIANT": [],
        "DC'D": []
    }
    write_txt(str(p), header, summary, sections)
    s = p.read_text(encoding="utf-8")
    assert "Jane" not in s and "Doe" not in s
    assert "201-1 (AM)" in s and "Hold if SBP > 160" in s and "BP 165/70" in s
