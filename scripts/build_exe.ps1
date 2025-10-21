param(
    [string]$Python = "python",
    [string]$Venv = ".venv"
)

if (!(Test-Path $Venv)) {
    & $Python -m venv $Venv
}

& "$Venv/Scripts/Activate.ps1"
& $Python -m pip install --upgrade pip
& $Python -m pip install -r requirements.txt pyinstaller
& $Python -m PyInstaller --clean --onefile --name HushDesk hushdesk/app.py --collect-data zoneinfo
