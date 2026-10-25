#!/usr/bin/env bash
# EarthIQ Basemap · AI base map designer. Starts the local server on http://127.0.0.1:8000
set -e
cd "$(dirname "$0")"

# ---------------------------------------------------------------------------
# uv (Python package manager)
# ---------------------------------------------------------------------------
if ! command -v uv >/dev/null 2>&1; then
  echo "uv not found - installing…"
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
fi

# ---------------------------------------------------------------------------
# Python backend (uv project, locked in uv.lock)
# ---------------------------------------------------------------------------
uv sync

# ---------------------------------------------------------------------------
# React frontend (built to frontend/dist, served by the backend)
# ---------------------------------------------------------------------------
build_frontend() {
  if ! command -v npm >/dev/null 2>&1; then
    echo "⚠  npm not found, the web UI will not be built (API still works at /api/health)." >&2
    return 0
  fi
  if [ ! -f frontend/dist/index.html ] || [ "${REBUILD:-0}" = "1" ]; then
    echo "Installing frontend dependencies…"
    ( cd frontend && npm install --no-audit --no-fund )
    echo "Building frontend…"
    ( cd frontend && npm run build )
  fi
}

# `run.sh --dev` runs the Vite dev server (hot reload) + the API in parallel.
if [ "$1" = "--dev" ]; then
  echo "Installing frontend dependencies…"
  ( cd frontend && npm install --no-audit --no-fund )
  echo "API  → http://127.0.0.1:8000"
  echo "Web  → http://127.0.0.1:5173  (proxies /api to :8000)"
  ( .venv/bin/python -m uvicorn server.main:app --host 127.0.0.1 --port "${PORT:-8000}" &
    ( cd frontend && npm run dev )
    wait )
  exit 0
fi

build_frontend

PORT="${PORT:-8000}"
HOST="${HOST:-127.0.0.1}"
echo "EarthIQ Basemap starting on http://$HOST:$PORT"
exec .venv/bin/python -m uvicorn server.main:app --host "$HOST" --port "$PORT"
