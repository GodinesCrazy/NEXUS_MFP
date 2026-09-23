$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    Write-Host "No existe .venv. Ejecuta primero .\setup.ps1" -ForegroundColor Yellow
    exit 1
}

& $python ".\src\nexus_mfp.py" @args
