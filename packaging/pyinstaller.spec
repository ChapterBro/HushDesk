# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
import sys

from PyInstaller.utils.hooks import (
    collect_all,
    collect_data_files,
    collect_dynamic_libs,
    collect_submodules,
)


SPEC_PATH = Path(sys.argv[0]).resolve()
BASE_DIR = SPEC_PATH.parent.parent
APP_ENTRY = str(BASE_DIR / "src" / "hushdesk" / "win_entry" / "gui_main.py")


def _safe_collect_all(pkg: str):
    try:
        return collect_all(pkg)
    except Exception:
        return ([], [], [])


pymupdf_datas, pymupdf_binaries, pymupdf_hidden = _safe_collect_all("pymupdf")
pymupdf_dlls = collect_dynamic_libs("pymupdf")
pymupdf_fonts_hidden = []
try:
    pymupdf_fonts_hidden = collect_submodules("pymupdf_fonts")
except Exception:
    pymupdf_fonts_hidden = []

pdfminer_datas, pdfminer_binaries, pdfminer_hidden = _safe_collect_all("pdfminer")
pdfplumber_datas, pdfplumber_binaries, pdfplumber_hidden = _safe_collect_all("pdfplumber")
tkdnd_datas, tkdnd_binaries, tkdnd_hidden = _safe_collect_all("tkinterdnd2")
hushdesk_datas, hushdesk_binaries, hushdesk_hidden = _safe_collect_all("hushdesk")

hiddenimports = (
    pymupdf_hidden
    + pymupdf_fonts_hidden
    + pdfminer_hidden
    + pdfplumber_hidden
    + tkdnd_hidden
    + hushdesk_hidden
    + ["fitz", "pymupdf", "pymupdf_fonts"]
)

datas = (
    pymupdf_datas
    + pdfminer_datas
    + pdfplumber_datas
    + tkdnd_datas
    + hushdesk_datas
    + collect_data_files("tzdata")
    + [
        (str(BASE_DIR / "src" / "hushdesk" / "config" / "building_master.json"), "hushdesk/config"),
        (str(BASE_DIR / "fixtures" / "bridgeman_sample.json"), "fixtures"),
    ]
)

binaries = (
    pymupdf_binaries
    + list(pymupdf_dlls)
    + pdfminer_binaries
    + pdfplumber_binaries
    + tkdnd_binaries
    + hushdesk_binaries
)


a = Analysis(
    [APP_ENTRY],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="HushDesk",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="HushDesk",
)
