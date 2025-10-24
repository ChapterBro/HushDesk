$ErrorActionPreference = "Stop"
$Repo = Split-Path -Parent $MyInvocation.MyCommand.Path
cd $Repo\..\..  # move to repo root if script placed under tools/windows

python -m venv .venv
.\.venv\Scripts\Activate.ps1

python - <<PY
import sys, subprocess
pkgs = ["pyinstaller"]
subprocess.check_call([sys.executable, "-m", "pip", "install", *pkgs])
print("OK: pyinstaller installed")
PY

mkdir -Force .\src\hushdesk_win_privacy | Out-Null
Copy-Item .\tools\windows\privacy_runtime_win.py .\src\hushdesk_win_privacy\__init__.py -Force

pyinstaller ^
  --name HushDesk ^
  --onefile ^
  --noconsole ^
  --clean ^
  --hidden-import fitz ^
  --add-data "fixtures;fixtures" ^
  .\src\hushdesk\win_entry\windows_main.py

Write-Host "Built: dist\HushDesk.exe"
