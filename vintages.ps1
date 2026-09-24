$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    throw "No existe .venv. Ejecuta primero .\setup.ps1"
}

$env:PYTHONPATH = Join-Path $PSScriptRoot "src"
& $python -m nexus_data.alfred @args
exit $LASTEXITCODE
