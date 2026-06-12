#!/usr/bin/env bash
# One-command local dev (no Docker): API on :8000, web on :3000.
set -euo pipefail
cd "$(dirname "$0")"

echo "── Nomi API (FastAPI) ──────────────────────────────"
pushd backend > /dev/null
if [ ! -d .venv ]; then python3 -m venv .venv; fi
source .venv/bin/activate
pip install -q -r requirements.txt
uvicorn app.main:app --reload --port 8000 &
API_PID=$!
popd > /dev/null
trap 'kill "$API_PID" 2>/dev/null || true' EXIT

echo "── Nomi web (Next.js) ──────────────────────────────"
cd frontend
[ -f .env.local ] || cp .env.local.example .env.local
[ -d node_modules ] || npm install
npm run dev
