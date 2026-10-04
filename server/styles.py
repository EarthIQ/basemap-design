"""Loading and normalising OpenFreeMap MapLibre styles.

The style JSONs are authored with a __TILEJSON_DOMAIN__ placeholder so the
same file can be served from any host. We fetch the raw file once, cache it
on disk, and substitute the current tile base URL each time we resolve it.
This means the user can switch the base URL (public vs self-hosted) without
re-downloading anything.

Robustness: network fetches are retried once and, if the network is down, we
fall back to whatever is already cached on disk so the app keeps working
offline after the first load.
"""
from __future__ import annotations

import copy
import json
import time
from pathlib import Path
from typing import Any

import httpx

from . import settings

_PLACEHOLDER = "__TILEJSON_DOMAIN__"
_http: httpx.Client | None = None


class StyleLoadError(RuntimeError):
    """Raised when a style cannot be resolved (and no cache is available)."""


def _client() -> httpx.Client:
    global _http
    if _http is None:
        _http = httpx.Client(timeout=httpx.Timeout(30.0, connect=10.0))
    return _http


def _raw_cache_path(name: str) -> Path:
    return settings.STYLES_DIR / f"{name}.raw.json"


def _read_cache(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text())
    except Exception:  # corrupt cache file -> treat as missing
        return None


def fetch_raw_style(name: str, force: bool = False) -> dict[str, Any]:
    """Return the raw style (still containing the domain placeholder).

    Served from the OpenFreeMap styles repo; cached to disk so repeat loads
    are instant and offline-tolerant after the first fetch. On a network
    failure we transparently fall back to the (possibly stale) cache.
    """
    cache_path = _raw_cache_path(name)
    if not force:
        cached = _read_cache(cache_path)
        if cached is not None:
            age = time.time() - cache_path.stat().st_mtime
            # Re-fetch the (small) style file at most once a day to pick up
            # updates, but keep serving the cache in the meantime.
            if age < 86_400:
                return cached

    url = settings.STYLES_REPO_RAW.format(name=name)
    last_err: Exception | None = None
    for attempt in range(2):  # initial try + one retry
        try:
            resp = _client().get(url)
            resp.raise_for_status()
            style = resp.json()
            cache_path.write_text(json.dumps(style))
            return style
        except (httpx.HTTPError, ValueError) as exc:
            last_err = exc
            if attempt == 0:
                time.sleep(0.5)  # brief backoff before the retry

    # Network failed: fall back to whatever we have cached, if anything.
    cached = _read_cache(cache_path)
    if cached is not None:
        return cached
    raise StyleLoadError(
        f"Could not load base style '{name}' and no local cache is available "
        f"(last error: {last_err}). Check your network or pre-fetch the style."
    )


def resolve_style(name: str, tile_base_url: str | None = None) -> dict[str, Any]:
    """Return a fully-resolved style ready for MapLibre.

    The domain placeholder is replaced with ``tile_base_url`` (defaulting to
    the configured public instance). Returns a deep copy so callers can
    mutate safely.
    """
    raw = fetch_raw_style(name)
    text = json.dumps(raw)
    base = (tile_base_url or settings.TILE_BASE_URL).rstrip("/")
    # The style templates embed the placeholder as a *host* after a scheme,
    # e.g. "https://__TILEJSON_DOMAIN__/sprites/...". Substitute the host only,
    # otherwise we get "https://https://...".
    host = base.split("://", 1)[1] if "://" in base else base
    text = text.replace(_PLACEHOLDER, host)
    return copy.deepcopy(json.loads(text))


def list_styles() -> list[dict[str, Any]]:
    """Metadata about the available base styles."""
    out = []
    for name in settings.BASE_STYLES:
        try:
            style = resolve_style(name)
            out.append(
                {
                    "name": name,
                    "layers": len(style.get("layers", [])),
                    "version": style.get("version"),
                }
            )
        except Exception as exc:  # network dependent
            out.append({"name": name, "error": str(exc)})
    return out


def tile_endpoints(tile_base_url: str | None = None) -> dict[str, str]:
    """Human-readable reference of the underlying OpenFreeMap endpoints."""
    base = (tile_base_url or settings.TILE_BASE_URL).rstrip("/")
    return {
        "tilejson": f"{base}/planet",
        "vector_tiles": f"{base}/planet/{{z}}/{{x}}/{{y}}.pbf",
        "natural_earth": f"{base}/natural_earth/ne2sr/{{z}}/{{x}}/{{y}}.png",
        "sprites": f"{base}/sprites/ofm_f384/ofm",
        "glyphs": f"{base}/fonts/Noto Sans Regular/{{range}}.pbf",
    }
