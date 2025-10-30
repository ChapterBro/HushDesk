- src/hushdesk/ui/app.py
- src/hushdesk/pdf/backends.py
- src/hushdesk/core/pdf/reader.py
- src/hushdesk/version.py
- src/hushdesk/core/export/checklist_render.py
- src/hushdesk/src/hushdesk/fixtures/bridgeman_sample.json
- tools/pyinstaller/hushdesk.spec

## Implemented
- Added first-class drag-and-drop entry for MAR PDFs/fixtures with unified `_on_file_chosen` logic and friendly validation for unsupported paths.
- Replaced the legacy “PDF backend disabled” message with the “Can’t read this MAR yet” modal; the dialog offers to launch the Bridgeman sample via Quick Actions and guides exports to stay PHI-safe.
- Introduced hall override UX (text entry + combobox populated from `building_master.json`), persistent override state, and propagation into headers/exports.
- Bundled a PHI-free fixture (`src/hushdesk/fixtures/bridgeman_sample.json`) and wired Quick Actions → Load Fixture → Bridgeman (sample) for instant demos.
- Added version detection (`src/hushdesk/version.py`), footer preflight badge (MuPDF/pdfplumber/DnD), and updated TXT export footer with `v{APP_VERSION}`.
- Prepared PyInstaller spec scaffolding that collects pymupdf/pdfplumber/pdfminer/tkinterdnd2 assets for Windows packaging.

## Manual Smoke (pending)
- Real MAR PDF through Quick Check/Run Audit (verify hall auto-detect or override, TXT export).
- Bridgeman sample via Quick Actions (counters > 0, TXT save).
- Drag-and-drop for `.pdf` and `.json`.
- Backend fallback matrix: PyMuPDF only, pdfplumber only, both missing (modal appears + sample loads).
- Offline run (Wi-Fi disabled) with UI + exports.

_Next session: finish packaging datas, document build command, record above smokes, and prepare PR with generated EXE._

----------------------------------------------------------------
## 2025‑10‑29 — PDF parser & UI upgrades + shipping checklist

**Why this matters (quick):** Today’s work makes the MAR pipeline tougher and more private: cleaner time parsing, PI‑safe headers, deterministic cell cleanup, better “Room ###” block detection, and a simpler, friendlier UI flow. We also locked in SBP/Pulse phrase handling so rules read like humans say them.

### What changed (today)
- **Rules language** — accepts plain phrases:
  - Normalizes **“SBP less than …”**, **“SBP greater than …”**, **“Pulse less than …”** into the existing comparator symbols before parsing.
  - Hooked straight into the strict holds parser loop so the regex sees canonical text.
- **Time parsing** — new pdf/timeparse.py:
  - Eats messy tokens (9am, 9 AM, 9:00p, 21:00, 2100) → canonical HH:MM.
  - Preserves AM/PM intent while normalizing spacing/case; supports 24‑hour too.
- **PII scrubbing + cell cleanup**:
  - pdf/header_scrub.py removes header lines that can carry PHI/PII before anything is cached or written.
  - pdf/celljoin.py gives deterministic token joining (hyphens/dashes/soft breaks cleaned predictably).
- **Room block finder** — pdf/mar_blocks.py:
  - Finds **“Room 100/200/300/400”** anchors and groups schedule cells under each block; tolerates minor whitespace/layout drift.
- **New MAR parser** — pdf/mar_parser.py:
  - Opens the PDF, scrubs headers, locates room blocks, emits sanitized cell strings + per‑dose records (med, raw time, normalized time/range, and notes).
  - Clear error path: *“no schedule grid found”* if anchors are missing, instead of hard crashes.
- **UI wire‑up**:
  - Quick Check / Run Audit call the new parser and show a lightweight dose preview.
  - Friendly modal replaces the old “PDF backend disabled” message; drag‑and‑drop and Browse share the same code path.
- **Packaging**:
  - PyInstaller spec collects pymupdf/pdfplumber/pdfminer.six/	kinterdnd2 and 	zdata.
  - Version stamp displayed in footer/export; offline‑only behavior remains.

### Guardrails (privacy)
- Parser drops/zeroes header lines before any in‑memory caching for exports.
- Exports only contain non‑identifying fields (hall tag, date, room number, dose metadata, compliance status).
- No network calls. No PHI written to disk.

---

## “Practically Finished” Ship Checklist

**Parser (PDF → dose records)**
- [ ] Time tokens normalize correctly across forms (9am, 9 AM, 9:00 p, 21:00, 2100) → HH:MM.
- [ ] SBP/Pulse phrases normalize: “SBP less than X”, “SBP greater than Y”, “Pulse less than Z”
.- [ ] Room block anchors recognized for **100 / 200 / 300 / 400** layouts, including slight spacing/line‑wrap drift.
- [ ] Cell joiner removes soft hyphens/em‑/en‑dash noise without eating real minus signs.
- [ ] Dose record fields present: {room, med text, scheduled raw token, normalized time, notes/hold code token}.
- [ ] Parser returns a clear error (no crash) when the schedule grid isn’t found or the file isn’t a MAR.

**Classification (valid/hold/compliant/DC’d)**
- [ ] Hold codes (4, 6, 11, 12, 15) and “X’d out / DC’d” are detected from the sanitized cell text.
- [ ] Non‑hold “given” entries classify as **Compliant** when within rule; otherwise flagged.
- [ ] Rules engine reads the normalized phrases (SBP/Pulse) and applies thresholds consistently.
- [ ] Edge cases logged with a short, PI‑safe reason (e.g., “SBP rule applied: 92 < 100 at 09:00”).

**UI/UX**
- [ ] Drag‑and‑drop and Browse share one path; both auto‑run Quick Check on selection.
- [ ] Friendly modal appears for missing PDF backend or unparseable files; no technical jargon.
- [ ] Audit date + hall override work even if the MAR header is scrubbed.
- [ ] Footer preflight shows backends status (MuPDF / fallback / DnD / Safety) and version.

**Outputs**
- [ ] TXT summary exports list **Reviewed / Hold‑Miss / Held‑OK / Compliant / DC’d** counts per hall.
- [ ] No patient names, MRNs, or DOBs appear in any file or log.
- [ ] Deterministic formatting (stable ordering, stable spacing) for easy diff/QA.

**Packaging & Offline**
- [ ] PyInstaller EXE launches on a clean Windows box without Python installed.
- [ ] All runtime libs collected (pymupdf, pdfplumber, pdfminer.six, tkinterdnd2, tzdata).
- [ ] App remains fully offline; no telemetry.

**Docs**
- [ ] README: quick start, offline guarantee, privacy stance, how to report a false positive.
- [ ] BUILD_NOTES.md updated (this section), plus any known limitations.
- [ ] Version bump and changelog entry for this release.

**Go/No‑Go**
- [ ] Run a quick pass on a MAR for **each** hall (100/200/300/400) and spot‑check 3–5 doses per hall.
- [ ] If any false negatives/positives appear, capture the sanitized cell text and rule reason to triage.

---

Operator note: this section was appended automatically by tooling; content is PI‑safe by design.
----------------------------------------------------------------
