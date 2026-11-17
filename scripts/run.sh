#!/usr/bin/env bash
# Production run: build the frontend, then serve API + frontend from one port (8000).
set -euo pipefail
cd "$(dirname "$0")/.."

if [ ! -d .venv ]; then
  echo "Creating Python virtual environment..."
  python3 -m venv .venv
fi
source .venv/bin/activate
pip install -q -r backend/requirements.txt

echo "Building frontend..."
(cd frontend && npm install --silent && npm run build)

echo "Starting server on http://localhost:8000 ..."
cd backend
exec python -m uvicorn app.main:app --host 0.0.0.0 --port "${PORT:-8000}"
