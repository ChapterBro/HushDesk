$ErrorActionPreference = "Stop"
Write-Host "Running self-check..."
& "$PSScriptRoot\..\..\dist\HushDesk.exe" self-check
Write-Host "Now build installer with Inno (optional): iscc tools\windows\installer.iss"
