# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all, collect_data_files

pymupdf_datas, pymupdf_binaries, pymupdf_hidden = collect_all('pymupdf')
pdfplumber_datas, pdfplumber_binaries, pdfplumber_hidden = collect_all('pdfplumber')
pdfminer_datas, pdfminer_binaries, pdfminer_hidden = collect_all('pdfminer')
tkdnd_datas, tkdnd_binaries, tkdnd_hidden = collect_all('tkinterdnd2')
hushdesk_datas, hushdesk_binaries, hushdesk_hidden = collect_all('hushdesk')

hiddenimports = pymupdf_hidden + pdfplumber_hidden + pdfminer_hidden + tkdnd_hidden + hushdesk_hidden + ['fitz']
datas = (
    pymupdf_datas
    + pdfplumber_datas
    + pdfminer_datas
    + tkdnd_datas
    + hushdesk_datas
    + collect_data_files('tzdata')
    + [
        ('src/hushdesk/config/building_master.json', 'hushdesk/config'),
        ('fixtures/bridgeman_sample.json', 'fixtures'),
    ]
)
binaries = pymupdf_binaries + pdfplumber_binaries + pdfminer_binaries + tkdnd_binaries + hushdesk_binaries


a = Analysis(
    ['src\\hushdesk\\win_entry\\gui_main.py'],
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
    name='HushDesk',
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

