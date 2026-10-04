"""EarthIQ server: FastAPI app wiring the agent, design engine and UI together."""
from __future__ import annotations

import json
import threading
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from . import agent, design, llm, settings, styles

app = FastAPI(title="EarthIQ - AI base map designer", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)

# Runtime, user-overridable provider choice (set by /api/settings).
settings.CURRENT_PROVIDER = "ollama"
DEFAULT_BASE_STYLE = "positron"

# ---------------------------------------------------------------------------
# Session state (single-user local tool) - the style is the source of truth.
# ---------------------------------------------------------------------------
_SESSION_LOCK = threading.Lock()
_SESSION: dict[str, Any] = {"style": {}, "history": [], "name": None}


def _init_session(base_style: str = DEFAULT_BASE_STYLE) -> None:
    try:
        style = styles.resolve_style(base_style, settings.TILE_BASE_URL)
        style["name"] = f"earthiq:{base_style}"
    except Exception:
        style = _minimal_style()
        base_style = "minimal"
    _SESSION["style"] = style
    _SESSION["history"] = []
    _SESSION["name"] = base_style


def _minimal_style() -> dict[str, Any]:
    base = settings.TILE_BASE_URL.rstrip("/")
    return {
        "version": 8,
        "name": "earthiq:minimal",
        "sources": {
            "openmaptiles": {
                "type": "vector",
                "tiles": [f"{base}/planet/v0/{{z}}/{{x}}/{{y}}.pbf"],
            },
        },
        "sprite": f"{base}/sprites/ofm_f384/ofm",
        "glyphs": f"{base}/fonts/Noto Sans Regular/{{range}}.pbf",
        "layers": [
            {"id": "background", "type": "background",
             "paint": {"background-color": "#eef1f5"}}
        ],
    }


try:
    if not _SESSION["style"]:
        _init_session()
except Exception:  # pragma: no cover - network dependent at import time
    pass


def _repaint_domains() -> None:
    """Re-point sprite/glyph/source asset URLs to the current tile base URL."""
    base = settings.TILE_BASE_URL.rstrip("/")
    style = _SESSION["style"]
    if not style:
        return
    style["sprite"] = f"{base}/sprites/ofm_f384/ofm"
    style["glyphs"] = f"{base}/fonts/{{fontstack}}/{{range}}.pbf"
    for src in (style.get("sources") or {}).values():
        if not isinstance(src, dict):
            continue
        if src.get("type") == "vector":
            src["url"] = f"{base}/planet"
        elif src.get("type") == "raster":
            src["tiles"] = [f"{base}/natural_earth/ne2sr/{{z}}/{{x}}/{{y}}.png"]


def _llm_config() -> dict[str, Any]:
    return {
        "provider": getattr(settings, "CURRENT_PROVIDER", "ollama"),
        "baseUrl": settings.OLLAMA_BASE_URL,
        "model": settings.DEFAULT_OLLAMA_MODEL,
        "openaiBaseUrl": settings.OPENAI_BASE_URL,
        "openaiModel": settings.OPENAI_MODEL,
        "apiKey": settings.OPENAI_API_KEY,
    }


def _normalize_provider(provider: str | None) -> str | None:
    """Map the many ways a client can name a provider to our canonical form."""
    if provider is None:
        return None
    p = provider.strip().lower().replace("-", "_").replace(" ", "_")
    if p in ("ollama",):
        return "ollama"
    if p in ("openai", "openai_compatible", "openai-compatible", "openrouter",
             "groq", "together", "lm_studio", "custom"):
        return "openai"
    return None


def _apply_provider_override(provider: str | None, model: str | None) -> None:
    """Persist a per-request provider/model choice into settings for the turn."""
    norm = _normalize_provider(provider)
    if norm:
        settings.CURRENT_PROVIDER = norm
    if model:
        if getattr(settings, "CURRENT_PROVIDER", "ollama") == "ollama":
            settings.DEFAULT_OLLAMA_MODEL = model
        else:
            settings.OPENAI_MODEL = model


def _sse(event: dict) -> str:
    return f"data: {json.dumps(event, ensure_ascii=False)}\n\n"


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------
class SettingsIn(BaseModel):
    provider: str | None = None
    ollamaBaseUrl: str | None = None
    ollamaModel: str | None = None
    openaiBaseUrl: str | None = None
    openaiModel: str | None = None
    openaiApiKey: str | None = None
    tileBaseUrl: str | None = None


class ChatIn(BaseModel):
    message: str
    provider: str | None = None
    model: str | None = None


class ApplyIn(BaseModel):
    name: str
    args: dict | None = None


class LoadIn(BaseModel):
    name: str


class ImportIn(BaseModel):
    style: dict
    name: str | None = None


# ---------------------------------------------------------------------------
# Introspection / design endpoints
# ---------------------------------------------------------------------------
@app.get("/api/health")
def health() -> dict:
    return {
        "ok": True,
        "ollama": llm.check_ollama(settings.OLLAMA_BASE_URL),
        "tileBaseUrl": settings.TILE_BASE_URL,
        "provider": getattr(settings, "CURRENT_PROVIDER", "ollama"),
        "model": settings.DEFAULT_OLLAMA_MODEL,
        "baseStyles": settings.BASE_STYLES,
        "endpoints": styles.tile_endpoints(),
    }


@app.get("/api/settings")
def get_settings() -> dict:
    return {
        "provider": getattr(settings, "CURRENT_PROVIDER", "ollama"),
        "ollama": {"baseUrl": settings.OLLAMA_BASE_URL,
                    "model": settings.DEFAULT_OLLAMA_MODEL},
        "openai": {"baseUrl": settings.OPENAI_BASE_URL, "model": settings.OPENAI_MODEL,
                    "hasKey": bool(settings.OPENAI_API_KEY)},
        "tileBaseUrl": settings.TILE_BASE_URL,
        "baseStyles": settings.BASE_STYLES,
    }


@app.post("/api/settings")
def set_settings(body: SettingsIn) -> dict:
    norm = _normalize_provider(body.provider)
    if norm:
        settings.CURRENT_PROVIDER = norm
    if body.ollamaBaseUrl:
        settings.OLLAMA_BASE_URL = body.ollamaBaseUrl.rstrip("/")
    if body.ollamaModel:
        settings.DEFAULT_OLLAMA_MODEL = body.ollamaModel
    if body.openaiBaseUrl:
        settings.OPENAI_BASE_URL = body.openaiBaseUrl.rstrip("/")
    if body.openaiModel:
        settings.OPENAI_MODEL = body.openaiModel
    if body.openaiApiKey is not None:
        settings.OPENAI_API_KEY = body.openaiApiKey
    if body.tileBaseUrl:
        settings.TILE_BASE_URL = body.tileBaseUrl.rstrip("/")
        with _SESSION_LOCK:
            _repaint_domains()
    return get_settings()


@app.get("/api/models")
def api_models(provider: str | None = None) -> dict:
    """Best-effort list of models for a provider (for the model picker)."""
    p = _normalize_provider(provider) or getattr(settings, "CURRENT_PROVIDER", "ollama")
    config = _llm_config()
    config["provider"] = p
    try:
        models = llm.list_models(config)
    except Exception:
        models = []
    return {
        "provider": p,
        "models": models,
        "default": settings.DEFAULT_OLLAMA_MODEL if p == "ollama" else settings.OPENAI_MODEL,
    }


@app.get("/api/palettes")
def palettes() -> dict:
    return {"palettes": design._palettes_summary()}


@app.get("/api/styles")
def api_styles() -> dict:
    return {"baseStyles": styles.list_styles(), "current": _SESSION.get("name")}


@app.post("/api/session/load")
def load_session(body: LoadIn) -> dict:
    if body.name not in settings.BASE_STYLES:
        raise HTTPException(400, f"Unknown base style '{body.name}'.")
    with _SESSION_LOCK:
        new = styles.resolve_style(body.name, settings.TILE_BASE_URL)
        new["name"] = f"earthiq:{body.name}"
        _SESSION["style"] = new
        _SESSION["history"] = []
        _SESSION["name"] = body.name
    return {"ok": True, "name": body.name,
            "actions": [{"type": "set_style", "style": _SESSION["style"]}]}


@app.post("/api/session/import")
def import_session(body: ImportIn) -> dict:
    """Load a previously-exported MapLibre style JSON as the current design."""
    style = body.style
    if not isinstance(style, dict) or "version" not in style or "layers" not in style:
        raise HTTPException(
            400, "Not a valid MapLibre style JSON (needs `version` and `layers`)."
        )
    name = (body.name or "imported").strip() or "imported"
    with _SESSION_LOCK:
        style["name"] = f"earthiq:{name}"
        _SESSION["style"] = style
        _SESSION["history"] = []
        _SESSION["name"] = name
    return {
        "ok": True,
        "name": name,
        "actions": [{"type": "set_style", "style": _SESSION["style"]}],
    }


@app.get("/api/session/style")
def session_style() -> dict:
    with _SESSION_LOCK:
        return json.loads(json.dumps(_SESSION["style"]))


@app.get("/api/session/overview")
def session_overview() -> dict:
    with _SESSION_LOCK:
        return design.style_overview(_SESSION["style"])


@app.post("/api/apply")
def apply_tool(body: ApplyIn) -> dict:
    """Run a single design tool (used by the manual inspector)."""
    with _SESSION_LOCK:
        result, actions = design.execute_tool(_SESSION["style"], body.name, body.args)
        overview = design.style_overview(_SESSION["style"])
    return {"result": result, "actions": actions, "overview": overview}


# ---------------------------------------------------------------------------
# AI chat (Server-Sent Events stream)
# ---------------------------------------------------------------------------
@app.post("/api/chat")
def chat_endpoint(body: ChatIn):
    message = (body.message or "").strip()
    if not message:
        raise HTTPException(400, "Message cannot be empty.")

    # Per-request provider/model overrides (persist to settings for the turn).
    _apply_provider_override(body.provider, body.model)

    def gen():
        try:
            for event in agent.run_agent(_SESSION, message):
                yield _sse(event)
        except Exception as exc:  # pragma: no cover - safety net
            yield _sse({"type": "error", "message": f"{type(exc).__name__}: {exc}"})
        yield "data: [DONE]\n\n"

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/api/session/reset")
def reset_session(body: LoadIn | None = None) -> dict:
    name = body.name if body and body.name else DEFAULT_BASE_STYLE
    with _SESSION_LOCK:
        _init_session(name)
    return {"ok": True, "name": _SESSION.get("name")}


# ---------------------------------------------------------------------------
# Static UI (built React app served as an SPA)
# ---------------------------------------------------------------------------
_DIST = settings.WEB_DIR


def _frontend_not_built() -> dict:
    return {
        "name": "EarthIQ",
        "message": (
            "The frontend build was not found. Run "
            "`cd frontend && npm install && npm run build`, then reload."
        ),
        "api": "/api/health",
    }


@app.get("/")
def index():
    path = _DIST / "index.html"
    if path.is_file():
        return FileResponse(str(path))
    return JSONResponse(_frontend_not_built(), status_code=503)


# Vite emits hashed bundles under dist/assets; serve them explicitly so the
# catch-all below can't shadow them.
if (_DIST / "assets").is_dir():
    app.mount("/assets", StaticFiles(directory=str(_DIST / "assets")), name="assets")


@app.get("/{path:path}")
def spa_fallback(path: str):
    """Serve any built file, falling back to index.html for SPA routes.

    API routes are registered earlier and take priority; unmatched /api/*
    paths correctly 404 instead of returning the SPA shell.
    """
    if path.startswith("api/") or path.startswith("web/"):
        raise HTTPException(404, "Not found")
    if not _DIST.is_dir():
        return JSONResponse(_frontend_not_built(), status_code=503)
    candidate = (_DIST / path).resolve()
    # Prevent path traversal outside the dist directory.
    if candidate.is_file() and str(candidate).startswith(str(_DIST.resolve())):
        return FileResponse(str(candidate))
    return FileResponse(str(_DIST / "index.html"))


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("server.main:app", host="127.0.0.1", port=8000, log_level="info")