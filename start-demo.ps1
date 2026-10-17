$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
if (-not (Test-Path .venv)) { python -m venv .venv }
& .\.venv\Scripts\python.exe -m pip install -r backend\requirements-demo.txt
$env:KATALYST_AI_PROVIDER = "demo"
$env:KATALYST_STORE = "sqlite"
$env:KATALYST_AUTH_MODE = "demo"
Set-Location backend
Write-Host "Open http://127.0.0.1:8000 in your browser"
& ..\.venv\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
