# PowerShell launcher for HushDesk GUI (Windows-first)
param()
$ErrorActionPreference = "Stop"
$REPO = Split-Path -Parent $MyInvocation.MyCommand.Definition
$ROOT = Resolve-Path "$REPO\.."
$env:PYTHONPATH = "$($ROOT.Path)\src;$env:PYTHONPATH"
python -m hushdesk.ui.app
