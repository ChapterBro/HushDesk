import os, sys, re, json, pathlib
root = pathlib.Path(__file__).resolve().parents[1]

def find(patterns, path):
    found = []
    for p in path.rglob("*.py"):
        try:
            s = p.read_text(encoding="utf-8")
        except:
            continue
        if all(re.search(pt, s, re.I|re.S) for pt in patterns):
            found.append(str(p.relative_to(root)))
    return found

res = {}
res["pdf_backends_file"] = (root/"src/hushdesk/pdf/backends.py").exists()
res["pdf_backends_defs"] = bool(find([r"class\\s+PdfUnavailable", r"def\\s+get_backend"], root/"src/hushdesk/pdf"))
res["ui_uses_backend"] = bool(find([r"get_backend", r"PdfUnavailable"], root/"src/hushdesk/ui"))
res["ui_has_dnd"] = bool(find([r"tkinterdnd2|TkinterDnD", r"drop_target_register|dnd_bind"], root/"src/hushdesk/ui"))
res["friendly_modal"] = bool(find([r"Can.?t\\s+read\\s+this\\s+MAR\\s+yet", r"Open\\s+Quick\\s+Actions"], root/"src/hushdesk/ui"))
res["hall_override"] = bool(find([r"Hall\\s+not\\s+found\\s+in\\s+header", r"Combobox|ttk\\.Combobox"], root/"src/hushdesk"))
res["bridgeman_sample_present"] = any("sample" in f for f in [str(p) for p in root.rglob("*.json") if "bridgeman" in str(p).lower()])
specs = list(root.rglob("*.spec"))
res["specs"] = [str(s.relative_to(root)) for s in specs]
spec_text = "".join((s.read_text(errors="ignore") for s in specs))
res["spec_collects_libs"] = all(w in spec_text for w in ["pymupdf","fitz","pdfplumber","pdfminer","tkinterdnd2"])
print(json.dumps(res, indent=2))
