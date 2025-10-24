# HushDesk

Local-first, HIPAA-safe. Primary export: TXT checklist (room & hall only).
Outcomes: HOLD-MISS · HELD-APPROPRIATE · COMPLIANT · DC'D. No UNCERTAIN.

Dev quickstart:
python -m venv .venv
. .venv/bin/activate
python -m pip install -e .
python -m pip install -U pytest ruff
pytest
CLI (scaffold):
python -m hushdesk.cli master-info

### Simulation (no PyMuPDF)
Run inside restricted environments:
bin/hush simtrial

### Simulation quick-check (no PDF, no network)
Run a fixture and print counts:
bin/hush simcheck fixtures/sample_sim_bridgeman_10-24-2025_dual.json

Expected output for the dual fixture:
Fixture: 10-24-2025 Bridgeman
Reviewed: 2 | Hold-Miss: 2 | Held-Appropriate: 0 | Compliant: 0 | DC'D: 0

Note on "Reviewed" in simulations:
Reviewed counts dose-level checks (each AM/PM due cell in the fixture with rules), even if an out-of-scope code yields no decision record. This mirrors real audits where the nurse reviewed the dose regardless of output chips.

### Simulation regression (no PDF)
Run both fixtures and assert expected counts:
bin/hush simregress

Outputs PASS/FAIL with exact deltas.

### Simulation quick-check #3 (given variants)
bin/hush simcheck fixtures/sample_sim_bridgeman_10-26-2025_given_variants.json
Expected:
Fixture: 10-26-2025 Bridgeman
Reviewed: 2 | Hold-Miss: 1 | Held-Appropriate: 0 | Compliant: 1 | DC'D: 0

Constants:
- Allowed held codes: {4,6,11,12,15}
- Given glyphs: √, ✓, ■, ✔

### Runtime toggles (default: secure)
- `--allow-network` (default OFF): permit network if explicitly needed.
- `--no-private-tmp` (default OFF): skip private TMP dir creation.
- `--allow-crashdialogs` (default OFF): allow OS crash UI.

Check current process lockdown:
python -m hushdesk.cli privacy-selfcheck
→ prints: private_tmp=<bool> deny_network=<bool> disable_crashdialogs=<bool>

### Counts-only mode
Use `--summary-only` to print counts without writing TXT/JSON files:
python -m hushdesk.cli bp-audit-sim --fixture fixtures/sample_sim_bridgeman_10-24-2025_dual.json --summary-only
Exit code is 2 if any Hold-Miss > 0, else 0.

### Administrative Director (built-in expert)
Get a non-PII repo digest for Codex context:
bin/hush ad-bootstrap

See docs/ADMINISTRATIVE_DIRECTOR.md for invariants, triage flow, and prompt templates.

## Windows Quickstart
- Runs completely offline; never stores PHI/PII.
- Drag & drop a MAR PDF, or use simulation fixtures.
- Quick Check shows counts; Run Audit writes a TXT (room+hall only) with Central timestamp.
- Self-check (frozen EXE): `HushDesk.exe self-check` → expect overall PASS.

