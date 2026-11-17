# Production run: build the frontend, then serve API + frontend from one port (8000).
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

if (-not (Test-Path ".venv")) {
    Write-Host "Creating Python virtual environment..."
    python -m venv .venv
}
& ".venv\Scripts\Activate.ps1"
pip install -q -r backend\requirements.txt

Write-Host "Building frontend..."
Push-Location frontend
npm install --silent
npm run build
Pop-Location

$port = if ($env:PORT) { $env:PORT } else { "8000" }
Write-Host "Starting server on http://localhost:$port ..."
Set-Location backend
python -m uvicorn app.main:app --host 0.0.0.0 --port $port
