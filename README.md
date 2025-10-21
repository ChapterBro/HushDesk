# HushDesk v0

HushDesk is a quiet, privacy-first desktop assistant for BP hold audits. Version 0 focuses exclusively on Medication Pass (MAR) PDFs and the SBP / HR parameters that govern a hold decision.

## Quick Start (Windows 11)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m hushdesk.app  # launch the UI
python -m hushdesk audit --in path\to\mar.pdf --out results.json  # headless audit
```

## Privacy defaults

* Room identifiers only are written by default.
* Export buttons prompt before adding medication names. `Cancel` aborts the export without creating a file.
* Diagnostics stay in-memory until you explicitly export.

## Rule policy

* Metrics: SBP and HR/Pulse only. DBP/diastolic readings are ignored.
* Operators: `<`, `>`, "less than/below/under", "greater than/above/over".
* Exclusive ranges: `between 110 and 150` or `110-150` / `110–150` with no inclusive language.
* Rejected: `=` , `≤`, `≥`, "at or below/above", "no less/more than", "inclusive", square brackets.
* Plausibility guardrails: SBP 50–250, HR 30–180.

## Date guardrail

* Default audit day is yesterday in America/Chicago (CT), daylight-saving safe.
* The UI's "Auto (Yesterday)" checkbox keeps the guardrail enabled. Uncheck to set a custom CT date.

## Hall detection

* Halls auto-detect by scanning room usage (Mercer 100s, Holaday 200s, Bridgman 300s, Morton 400s).
* Manual override only appears when the hall cannot be inferred.

## Limitations

* Version 0 processes PDFs only. HTML or other formats are unsupported.
* Only SBP/HR rules are understood; DBP ranges are ignored.
* Hold logic is restricted to Medication Pass compliance scenarios.

## Building the Windows EXE

```
powershell -File scripts/build_exe.ps1
```

The script provisions a virtual environment, installs dependencies, and creates a single-file executable with PyInstaller.
