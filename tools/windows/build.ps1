$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

# --- Paths: repo root is two levels up from this script (tools\windows) ---
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
Set-Location $RepoRoot
Write-Host "Repo root:" $RepoRoot

# --- Python env ------------------------------------------------------------
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
  python -m pip install -U pip wheel        | Out-Null
  python -m pip install -e .                | Out-Null
  python -m pip install pyinstaller tzdata pymupdf | Out-Null
}

# --- PyInstaller helper ----------------------------------------------------
function Build-Exe {
  param(
    [Parameter(Mandatory=$true)][string]$Name,
    [switch]$Console = $false
  )
  $pyi = ".\.venv\Scripts\pyinstaller.exe"
  $args = @(
    "--name", $Name,
    "--onefile",
    "--clean",
    "--hidden-import", "fitz",
    "--collect-data", "tzdata",
    "--collect-data", "hushdesk",
    "--add-data", "fixtures;fixtures",
    "--add-data", "src\hushdesk\config;hushdesk\config",
    "src\hushdesk\win_entry\windows_main.py"
  )
  if ($Console) { $args = @("--console") + $args } else { $args = @("--noconsole") + $args }
  & $pyi @args | Out-Host
  if ($LASTEXITCODE -ne 0) { throw "PyInstaller failed for $Name" }
}

# --- Offline smokes (console EXE → proper exit codes) ----------------------
function Run-Smokes {
  $cli = ".\dist\HushDeskCLI.exe"
  if (-not (Test-Path $cli)) { throw "Console EXE not found: $cli" }

  & $cli self-check | Out-Host

  & $cli bp-audit-sim --fixture "fixtures\sample_sim_bridgeman_10-25-2025_dcd_held.json" --summary-only
  $e1 = $LASTEXITCODE

  & $cli bp-audit-sim --fixture "fixtures\sample_sim_bridgeman_10-24-2025_dual.json" --summary-only
  $e2 = $LASTEXITCODE

  Write-Host ("[SMOKE] dcd_held exit={0} (expect 0), dual exit={1} (expect 2)" -f $e1, $e2)
  if ($e1 -ne 0 -or $e2 -ne 2) {
    Write-Warning "Unexpected exit codes. Check hushdesk.cli summary-only path or fixtures."
  }
}

# --- Main ------------------------------------------------------------------
Ensure-Venv
Build-Exe -Name "HushDesk"                    # GUI (no console window)
Build-Exe -Name "HushDeskCLI" -Console:$true  # Console (stdout + exit codes)
Run-Smokes
Write-Host "`nBuild done. EXEs in: $RepoRoot\dist"
