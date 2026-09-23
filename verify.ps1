$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    Write-Host "No existe .venv. Ejecuta primero .\setup.ps1" -ForegroundColor Yellow
    exit 1
}

$env:PYTHONPATH = Join-Path $PSScriptRoot "src"

& $python -m unittest discover -s tests -v
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

& $python -m compileall -q src tests
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

& $python -m pip check
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

Write-Host "NEXUS-MFP verification passed." -ForegroundColor Green
