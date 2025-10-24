import os, stat
from hushdesk.core.export.checklist_render import write_txt

def test_txt_is_private_mode(tmp_path):
    out = tmp_path / "out" / "bp.txt"
    header = {"date_str":"10-14-2025","hall":"Holaday","source":"file.pdf"}
    summary = {"reviewed":0,"hold_miss":0,"held_ok":0,"compliant":0,"dcd":0}
    sections = {"HOLD-MISS":[], "HELD-APPROPRIATE":[], "COMPLIANT":[], "DC'D":[]}
    write_txt(str(out), header, summary, sections)
    st = out.stat()
    assert stat.S_IMODE(st.st_mode) == 0o600
    assert stat.S_IMODE(out.parent.stat().st_mode) == 0o700
