$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

# Resolve repo root from this script’s location
$RepoRoot = (Resolve-Path "$PSScriptRoot\..").Path
Set-Location $RepoRoot
Write-Host "Repo root: $RepoRoot"

function Ensure-Venv {
  if (-not (Test-Path ".venv")) {
    if (Get-Command py -ErrorAction SilentlyContinue) {
      py -3.11 -m venv .venv
      if ($LASTEXITCODE -ne 0) { py -3 -m venv .venv }
    } else {
      python -m venv .venv
    }
  }
  . ".\.venv\Scripts\Activate.ps1"

  python -m pip install -U pip wheel                              | Out-Null
  python -m pip install -e .                                      | Out-Null  # hushdesk package (editable)
  python -m pip install pyinstaller tzdata pymupdf                | Out-Null  # packager + tzdata + fitz
}

function Build-Exe {
  param(
    [Parameter(Mandatory=$true)][string]$Name,
    [switch]$Console = $false,
    [string]$Entry   = "src\hushdesk\win_entry\windows_main.py"
  )
  $pyi = ".\.venv\Scripts\pyinstaller.exe"
  $args = @(
    "--name", $Name,
    "--onefile",
    "--clean",
    # ---- CRITICAL: collect all of our package (fixes 'No module named hushdesk.cli')
    "--collect-all", "hushdesk",
    # tzdata for America/Chicago, and required data files
    "--collect-data", "tzdata",
    "--add-data", "fixtures;fixtures",
    "--add-data", "src\hushdesk\config\building_master.json;hushdesk\config\building_master.json",
    # fitz (PyMuPDF) is imported lazily; force inclusion
    "--hidden-import", "fitz",
    $Entry
  )
  if ($Console) { $args = @("--console")  + $args } else { $args = @("--noconsole") + $args }

  & $pyi @args | Out-Host
  if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed for $Name" }
}

function Run-Smokes {
  $cli = ".\dist\HushDeskCLI.exe"
  if (-not (Test-Path $cli)) { throw "Console EXE not found: $cli" }

  # Privacy/runtime self-check line
  & $cli self-check | Out-Host

  # No-HOLD-MISS fixture → expect 0
  & $cli bp-audit-sim --fixture "fixtures\sample_sim_bridgeman_10-25-2025_dcd_held.json" --summary-only
  $e1 = $LASTEXITCODE

  # Dual HOLD-MISS fixture → expect 2
  & $cli bp-audit-sim --fixture "fixtures\sample_sim_bridgeman_10-24-2025_dual.json" --summary-only
  $e2 = $LASTEXITCODE

  Write-Host ("[SMOKE] dcd_held exit={0} (expect 0), dual exit={1} (expect 2)" -f $e1, $e2)
  if ($e1 -ne 0 -or $e2 -ne 2) { throw "Unexpected smoke exit codes: dcd_held=$e1, dual=$e2" }

  # Doctor alias should exist now
  & $cli doctor | Out-Host
}

# Main
Ensure-Venv
Build-Exe -Name "HushDesk"    -Console:$false -Entry "src\hushdesk\win_entry\gui_main.py"
Build-Exe -Name "HushDeskCLI" -Console:$true  -Entry "src\hushdesk\win_entry\windows_main.py"
Run-Smokes
Write-Host "`nBuild done. EXEs in: $RepoRoot\dist"


