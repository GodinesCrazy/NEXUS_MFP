$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    Write-Host "No existe .venv. Ejecuta primero .\setup.ps1" -ForegroundColor Yellow
    exit 1
}

$env:PYTHONPATH = Join-Path $PSScriptRoot "src"
Write-Host "Abre http://127.0.0.1:8765 en tu navegador." -ForegroundColor Cyan
& $python -m nexus_ui.server @args
