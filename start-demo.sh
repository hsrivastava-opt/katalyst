#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
if [ ! -d .venv ]; then python3 -m venv .venv; fi
source .venv/bin/activate
pip install -r backend/requirements-demo.txt
cd backend
export KATALYST_AI_PROVIDER=demo
export KATALYST_STORE=sqlite
export KATALYST_AUTH_MODE=demo
printf '\nKATALYST offline browser demo: http://127.0.0.1:8000\n'
uvicorn app.main:app --host 127.0.0.1 --port 8000
