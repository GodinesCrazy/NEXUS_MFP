$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot
$env:PYTHONPATH = Join-Path $PSScriptRoot "src"
py -3.10 -m nexus_forecast @args
exit $LASTEXITCODE
