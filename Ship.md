# HushDesk MAR Parsing – Recent Changes

## Summary
- Parallel, geometry-first MAR extractor that caches parameter strips with room hints for stable SBP/HR rule capture across 150+ page PDFs.
- Quick Review fallback now counts parametered doses (SBP/HR) using canonical hall rooms, shows sanitized highlight lines, and surfaces full preview rule lists for copy/paste.
- Drag-and-drop / backend pipeline wires hall detection metadata, service-day defaults, and parameter previews into the UI with selectable text cards and progress telemetry.
- Regression coverage added for layout blocks, parameter strips, quick-review canonicalization, and multi-line rule parsing to lock in the new behavior.

## Tests
- `.venv\Scripts\python.exe -m pytest`
