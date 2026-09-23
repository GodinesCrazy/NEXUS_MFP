$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not (Test-Path ".venv")) {
    py -3.10 -m venv .venv
}

& ".\.venv\Scripts\python.exe" -m pip install --upgrade pip
& ".\.venv\Scripts\python.exe" -m pip install -r requirements.txt

Write-Host "NEXUS-MFP preparado." -ForegroundColor Green
Write-Host "Ejecuta: .\run.ps1" -ForegroundColor Cyan
