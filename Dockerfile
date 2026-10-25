# syntax=docker/dockerfile:1
# EarthIQ Basemap — self-contained image: FastAPI backend + prebuilt React frontend.
#
#   docker build -t basemap .
#   docker run --rm -p 8000:8000 basemap
#   # → http://127.0.0.1:8000
#
# Ollama on the Docker host is reachable at http://host.docker.internal:11444
# (see docker-compose.yml for a ready-made setup).

# ---------------------------------------------------------------------------
# Stage 1 — build the React/TypeScript frontend
# ---------------------------------------------------------------------------
FROM node:22-alpine AS frontend
WORKDIR /build
# Install deps first for layer caching.
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
RUN npm run build

# ---------------------------------------------------------------------------
# Stage 2 — Python runtime (uv-managed, locked)
# ---------------------------------------------------------------------------
FROM python:3.12-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    UV_NO_CACHE=1

WORKDIR /app

# uv for fast, reproducible installs from uv.lock (pinned version).
COPY --from=ghcr.io/astral-sh/uv:0.9.26 /uv /usr/local/bin/uv

# Python dependencies (README.md is referenced by pyproject.toml).
COPY pyproject.toml uv.lock README.md LICENSE ./
RUN uv sync --frozen --no-dev

# Application code + the built frontend (server/.. = /app, dist at /app/frontend/dist).
COPY server/ ./server/
COPY --from=frontend /build/dist ./frontend/dist

# Run as an unprivileged user; data/ holds the cached base-map styles.
RUN useradd --create-home --shell /usr/sbin/nologin basemap \
    && mkdir -p /app/data \
    && chown -R basemap:basemap /app
USER basemap

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import sys, urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/api/health', timeout=4).status == 200 else 1)"

CMD ["uv", "run", "uvicorn", "server.main:app", "--host", "0.0.0.0", "--port", "8000"]