# Dev mode: backend with --reload on :8000 + Vite dev server with HMR on :5173 (proxies /api to :8000).
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

if (-not (Test-Path ".venv")) {
    python -m venv .venv
}
& ".venv\Scripts\Activate.ps1"
pip install -q -r backend\requirements.txt

$port = if ($env:PORT) { $env:PORT } else { "8000" }
$backend = Start-Process -PassThru -NoNewWindow python -ArgumentList "-m uvicorn app.main:app --reload --host 0.0.0.0 --port $port" -WorkingDirectory "backend"

try {
    Write-Host "Backend (reload) on http://localhost:$port"
    Write-Host "Frontend (HMR)    on http://localhost:5173"
    Push-Location frontend
    npm install --silent
    npm run dev
    Pop-Location
}
finally {
    Stop-Process -Id $backend.Id -ErrorAction SilentlyContinue
}
