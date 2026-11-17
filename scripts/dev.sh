#!/usr/bin/env bash
# Dev mode: backend with --reload on :8000 + Vite dev server with HMR on :5173 (proxies /api to :8000).
set -euo pipefail
cd "$(dirname "$0")/.."

if [ ! -d .venv ]; then
  python3 -m venv .venv
fi
source .venv/bin/activate
pip install -q -r backend/requirements.txt

(cd backend && python -m uvicorn app.main:app --reload --host 0.0.0.0 --port "${PORT:-8000}") &
BACKEND_PID=$!
trap 'kill $BACKEND_PID 2>/dev/null || true' EXIT

echo "Backend (reload) on http://localhost:${PORT:-8000}"
echo "Frontend (HMR)    on http://localhost:5173"
(cd frontend && npm install --silent && npm run dev)
