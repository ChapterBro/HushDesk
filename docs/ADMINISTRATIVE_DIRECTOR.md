# HushDesk — Administrative Director (AD) Kit

The AD is this repo’s built-in expert. It summarizes architecture, enforces invariants, and gives Codex exact levers to adjust behavior safely (no PHI, no side quests).

## Canon & Invariants
- **Privacy:** outputs show **hall + room only**; no names/IDs. JSON meta limited to **page/col**.
- **Files/dirs:** files **0600**, dirs **0700** (Windows: owner-only ACLs).
- **Decisions:** **HOLD-MISS**, **HELD-APPROPRIATE**, **COMPLIANT**, **DC'D**. No “UNCERTAIN.”
- **Vitals:** read from the **same date column**; prefer **BP row**, else **due cell**. Ignore DBP for hold logic.
- **Reviewed:** counts **dose-level** (unique AM/PM due cell), not decision-record count.
- **Strict rules only:** SBP/HR with `< N` or `> N`; discard `≤ ≥ = at/above at/below`.

## Triage Flow (fast, repeatable)
1. `bin/hush simregress` → must **PASS**.
2. To add/replicate a case: create `fixtures/*.json` (no PHI).
3. Change the **smallest** module (grid/blocks/tracks/tokenizer/holds/decide/constants).
4. Re-run `simregress`. Commit when green.

## Adjustment Cheatsheet (drop these edits into Codex)
- **Day column tolerance:** `core/layout/grid.py` → widen numeral band (e.g., ±14→±20) or merge-gap (6→10).
- **Vector-X detection:** `core/pdf/reader.py::has_vector_x` → relax angles 35–55°→30–60°, length ratio 0.6–1.6→0.35–1.9.
- **BP label variants:** `core/layout/tracks.py` → accept `B/P`, `BP:`, `Blood Pressure`.
- **Allowed held codes / given glyphs:** `core/constants.py` → update `ALLOWED_HELD_CODES`, `GIVEN_GLYPHS`.
- **“Hold if …” phrasing:** `core/engine/decide.py` → tune `notes` assembly.

## Useful Commands
- `bin/hush simtrial` — end-to-end sim TXT/JSON (no PyMuPDF).
- `bin/hush simcheck <fixture.json>` — quick counts.
- `bin/hush simregress` — PASS/FAIL across fixtures.
- `bin/hush ad-bootstrap` — non-PII repo digest for Codex context (halls, constants, modules).
