"""Runtime configuration and defaults for the EarthIQ base map designer.

Everything here can be overridden at runtime via the /api/settings endpoint
or environment variables, which is what allows the app to point at a
self-hosted OpenFreeMap instance or a different LLM provider without code
changes.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
STYLES_DIR = DATA_DIR / "styles"
# The built React app (Vite outputs to frontend/dist). The server serves this
# as a static SPA; during development run `npm run dev` in frontend/ instead.
WEB_DIR = PROJECT_ROOT / "frontend" / "dist"
STYLES_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Vector data source (OpenFreeMap, free & keyless)
# ---------------------------------------------------------------------------
# Base URL of the tile/style server. Can be the public instance or a
# self-hosted OpenFreeMap deployment (e.g. https://tiles.example.com).
TILE_BASE_URL = os.environ.get("EARTHIQ_TILE_BASE_URL", "https://tiles.openfreemap.org")

# The OpenFreeMap styles live in a separate repo. Each style.json uses the
# __TILEJSON_DOMAIN__ placeholder for the sprite / glyph / source host, which
# we substitute with TILE_BASE_URL at load time.
STYLES_REPO_RAW = (
    "https://raw.githubusercontent.com/hyperknot/openfreemap-styles/main/"
    "styles/{name}/style.json"
)

BASE_STYLES = ["bright", "dark", "fiord", "liberty", "positron"]

# ---------------------------------------------------------------------------
# LLM provider defaults
# ---------------------------------------------------------------------------
OLLAMA_BASE_URL = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11444")
DEFAULT_OLLAMA_MODEL = os.environ.get("EARTHIQ_OLLAMA_MODEL", "qwen3.8:27b")

# OpenAI-compatible fallback (OpenAI, OpenRouter, Groq, Together, LM Studio...)
OPENAI_BASE_URL = os.environ.get("OPENAI_BASE_URL", "https://openrouter.ai/api/v1")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "openai/gpt-4.1-mini")

# ---------------------------------------------------------------------------
# Agent behaviour
# ---------------------------------------------------------------------------
# Max tool-calling steps per user turn. Kept modest so a misbehaving model
# can't run away, while still allowing multi-step design work.
MAX_AGENT_STEPS = int(os.environ.get("EARTHIQ_MAX_STEPS", "8"))
# If a (usually small) model can't emit a proper tool call but says it as text,
# we can still act if it follows this exact line, which the system prompt
# teaches:   ACTION: apply_palette name=desert
ACTION_LINE_RE = re.compile(
    r"action\s*:\s*([a-zA-Z_]+)(?:\s+([a-zA-Z_-]+)\s*=\s*([^\s`]+))?", re.I
)
# HTTP timeout (seconds) for a single LLM request. Local small models can be
# slow to "think", so this is generous.
LLM_TIMEOUT = float(os.environ.get("EARTHIQ_LLM_TIMEOUT", "180"))


def default_settings() -> dict:
    """Return the current settings dict (mirrored to the UI)."""
    return {
        "tile_base_url": TILE_BASE_URL,
        "provider": "ollama",
        "ollama": {"baseUrl": OLLAMA_BASE_URL, "model": DEFAULT_OLLAMA_MODEL},
        "openai": {
            "baseUrl": OPENAI_BASE_URL,
            "model": OPENAI_MODEL,
            "hasKey": bool(OPENAI_API_KEY),
        },
        "baseStyles": BASE_STYLES,
    }
