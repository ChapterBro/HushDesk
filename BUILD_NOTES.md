- src/hushdesk/ui/app.py
- src/hushdesk/pdf/backends.py
- src/hushdesk/core/pdf/reader.py
- src/hushdesk/version.py
- src/hushdesk/core/export/checklist_render.py
- fixtures/bridgeman_sample.json
- tools/pyinstaller/hushdesk.spec

## Implemented
- Added first-class drag-and-drop entry for MAR PDFs/fixtures with unified `_on_file_chosen` logic and friendly validation for unsupported paths.
- Replaced the legacy “PDF backend disabled” message with the “Can’t read this MAR yet” modal; the dialog offers to launch the Bridgeman sample via Quick Actions and guides exports to stay PHI-safe.
- Introduced hall override UX (text entry + combobox populated from `building_master.json`), persistent override state, and propagation into headers/exports.
- Bundled a PHI-free fixture (`fixtures/bridgeman_sample.json`) and wired Quick Actions → Load Fixture → Bridgeman (sample) for instant demos.
- Added version detection (`src/hushdesk/version.py`), footer preflight badge (MuPDF/pdfplumber/DnD), and updated TXT export footer with `v{APP_VERSION}`.
- Prepared PyInstaller spec scaffolding that collects pymupdf/pdfplumber/pdfminer/tkinterdnd2 assets for Windows packaging.

## Manual Smoke (pending)
- Real MAR PDF through Quick Check/Run Audit (verify hall auto-detect or override, TXT export).
- Bridgeman sample via Quick Actions (counters > 0, TXT save).
- Drag-and-drop for `.pdf` and `.json`.
- Backend fallback matrix: PyMuPDF only, pdfplumber only, both missing (modal appears + sample loads).
- Offline run (Wi-Fi disabled) with UI + exports.

_Next session: finish packaging datas, document build command, record above smokes, and prepare PR with generated EXE._
