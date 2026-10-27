$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not (Test-Path -LiteralPath ".venv\Scripts\python.exe")) {
    Write-Error "Create the virtual environment first: py -3.12 -m venv .venv"
}

$python = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
& $python -m flask --app webapp db-ready
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Write-Host "Starting on http://127.0.0.1:5000 (press Ctrl+C to stop)."
& $python -m flask --app webapp run --host 127.0.0.1 --port 5000
exit $LASTEXITCODE
