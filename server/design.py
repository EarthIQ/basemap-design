"""Design engine: curated palettes + the set of style-editing "tools".

This module is the single source of truth for mutating a MapLibre style.
Both the LLM agent (via the tool dispatcher) and the manual inspector UI call
``execute_tool`` so the server-side style state and the rendered map always
agree. Every tool returns:

    result:  a small dict describing what happened (shown to the user/model)
    actions: a list of granular, ordered operations the browser applies to the
             live map (paint/layout/filter/visibility/background/config, or a
             full set_style for structural changes).

MapLibre property names are kebab-case (``fill-color``) but models often emit
snake_case (``fill_color``), so every property is normalised before use.
"""
from __future__ import annotations

import difflib
import json
import re
from typing import Any

from . import settings, styles

# ---------------------------------------------------------------------------
# Curated colour palettes
# ---------------------------------------------------------------------------
# Each palette maps *semantic roles* to concrete colours. ``apply_palette``
# pushes those onto the matching OpenFreeMap layers, recolouring the whole
# map cohesively in one step - the "make it a warm desert theme" superpower.
#
# Role targets are keyed to the real OpenFreeMap layer ids (verified against
# the shared OpenMapTiles schema). Missing layers are skipped, so a palette
# always works regardless of which base style is loaded.
PALETTES: dict[str, dict[str, Any]] = {}

PALETTES.update(
    {
        "ocean": {
            "label": "Ocean",
            "mode": "light",
            "description": "Cool, calm blues and teals over soft light land.",
            "tokens": {
                "background": "#eef6fb", "water": "#b6dcec", "waterway": "#8fc4e0",
                "land": "#f2f6f1", "park": "#cfe6c8", "building": "#dde5ea",
                "road_minor": "#ffffff", "road_major": "#f6e6b8", "motorway": "#f2c574",
                "railway": "#b0bcc4", "boundary": "#c3d0d8",
                "label": "#2c4a5e", "halo": "#ffffff",
            },
        },
        "arctic": {
            "label": "Arctic",
            "mode": "light",
            "description": "Very light, minimal, almost paper-white with icy water.",
            "tokens": {
                "background": "#f4f8fa", "water": "#cfe6f0", "waterway": "#b8d8e6",
                "land": "#f7faf8", "park": "#dcead9", "building": "#e4ebef",
                "road_minor": "#ffffff", "road_major": "#e9d9a6", "motorway": "#d9b25e",
                "railway": "#c2ccd2", "boundary": "#d2dce0",
                "label": "#3a4a52", "halo": "#ffffff",
            },
        },
        "desert": {
            "label": "Desert",
            "mode": "light",
            "description": "Warm sand tones with terracotta roads.",
            "tokens": {
                "background": "#f6efe2", "water": "#9fc4d4", "waterway": "#82aec0",
                "land": "#f2e7d0", "park": "#d9d8a6", "building": "#e3d3b8",
                "road_minor": "#ffffff", "road_major": "#e7c98f", "motorway": "#d69a52",
                "railway": "#cbb89a", "boundary": "#e0d0b0",
                "label": "#6b5334", "halo": "#fffaf0",
            },
        },
    }
)

PALETTES.update(
    {
        "canyon": {
            "label": "Canyon Sunset",
            "mode": "light",
            "description": "Dramatic warm oranges and pinks, like late light.",
            "tokens": {
                "background": "#fbe9dd", "water": "#f2a78f", "waterway": "#e98a6f",
                "land": "#f7dcc8", "park": "#e7b79a", "building": "#f0c9a8",
                "road_minor": "#fff2e6", "road_major": "#e8884a", "motorway": "#d1542a",
                "railway": "#c98a6a", "boundary": "#e6b491",
                "label": "#6e3418", "halo": "#fff3ea",
            },
        },
        "forest": {
            "label": "Forest",
            "mode": "light",
            "description": "Green and earthy, with muted teal water.",
            "tokens": {
                "background": "#eef2e6", "water": "#a9c9c0", "waterway": "#86b0a5",
                "land": "#eaf0e0", "park": "#bcd7a4", "building": "#d8ddc9",
                "road_minor": "#ffffff", "road_major": "#e6d3a0", "motorway": "#cfa24e",
                "railway": "#b3bda6", "boundary": "#ccd6bf",
                "label": "#2f4a2c", "halo": "#f4f8ef",
            },
        },
        "mono_light": {
            "label": "Monochrome Light",
            "mode": "light",
            "description": "Clean, neutral grays - a classic light base map.",
            "tokens": {
                "background": "#f8f9fa", "water": "#d5e3ec", "waterway": "#bcd2e0",
                "land": "#f8f9fa", "park": "#dcead2", "building": "#e6eaec",
                "road_minor": "#ffffff", "road_major": "#f0e2b6", "motorway": "#e5c069",
                "railway": "#c2cacf", "boundary": "#d3dbe0",
                "label": "#4a5560", "halo": "#ffffff",
            },
        },
        "mono_dark": {
            "label": "Monochrome Dark",
            "mode": "dark",
            "description": "Dark grays with crisp light lines and labels.",
            "tokens": {
                "background": "#1b1b1d", "water": "#23272b", "waterway": "#2f353b",
                "land": "#20242a", "park": "#2b332c", "building": "#2c3138",
                "road_minor": "#454b52", "road_major": "#5a616a", "motorway": "#7a828c",
                "railway": "#3a4048", "boundary": "#3a4048",
                "label": "#c9d0d6", "halo": "#000000",
            },
        },
    }
)

PALETTES.update(
    {
        "midnight": {
            "label": "Midnight",
            "mode": "dark",
            "description": "Deep navy with cool blue roads - a calm night theme.",
            "tokens": {
                "background": "#0e1626", "water": "#16233c", "waterway": "#1e3255",
                "land": "#121d31", "park": "#1a2a3a", "building": "#1d2b40",
                "road_minor": "#35507a", "road_major": "#4a7fd6", "motorway": "#63b3ff",
                "railway": "#2a3c5c", "boundary": "#24344f",
                "label": "#cfe0ff", "halo": "#050a14",
            },
        },
        "neon": {
            "label": "Neon",
            "mode": "dark",
            "description": "Near-black with vivid cyan and magenta accents.",
            "tokens": {
                "background": "#0a0a0a", "water": "#101820", "waterway": "#16324a",
                "land": "#0f1418", "park": "#12241a", "building": "#141a20",
                "road_minor": "#1f2a33", "road_major": "#22d3ee", "motorway": "#f0abfc",
                "railway": "#334155", "boundary": "#1f2937",
                "label": "#e5e7eb", "halo": "#000000",
            },
        },
        "pastel": {
            "label": "Pastel",
            "mode": "light",
            "description": "Soft, friendly pastels with a gentle lilac background.",
            "tokens": {
                "background": "#f3f0f7", "water": "#c3d9ea", "waterway": "#a9c6e0",
                "land": "#f1f4ec", "park": "#cfe3c4", "building": "#e2e0ec",
                "road_minor": "#ffffff", "road_major": "#f2d9a6", "motorway": "#edb868",
                "railway": "#ccd6e0", "boundary": "#d8d2e6",
                "label": "#5a5470", "halo": "#ffffff",
            },
        },
        "vintage": {
            "label": "Vintage Sepia",
            "mode": "light",
            "description": "Aged-paper sepia with muted, desaturated water.",
            "tokens": {
                "background": "#f0e6d2", "water": "#b9c7c2", "waterway": "#9fb3ac",
                "land": "#ece0c8", "park": "#d8d0a4", "building": "#ded2b6",
                "road_minor": "#f5eeda", "road_major": "#d8b978", "motorway": "#bd8b45",
                "railway": "#c4b590", "boundary": "#d8cba8",
                "label": "#5a4a2f", "halo": "#f7f0dd",
            },
        },
        "solar": {
            "label": "Solar Day",
            "mode": "light",
            "description": "High-contrast daytime look with vivid amber highways.",
            "tokens": {
                "background": "#f7f5f0", "water": "#aad3df", "waterway": "#86bdd1",
                "land": "#f6f2ea", "park": "#c9e0b8", "building": "#e3ded2",
                "road_minor": "#ffffff", "road_major": "#f4d472", "motorway": "#f0a92b",
                "railway": "#b0b6bc", "boundary": "#d8d2c4",
                "label": "#3a3f45", "halo": "#ffffff",
            },
        },
    }
)

# role -> list of (layer_id, property) that role colours. Every pair is applied
# independently; missing layers are skipped so a palette always "just works".
#
# OpenFreeMap styles are inconsistent about separators and even about layer
# names per base style (``bright`` uses ``highway-minor``/``waterway-river``,
# ``positron`` uses ``highway_minor``/``waterway``), so we list the *distinct*
# names we know about and rely on the fuzzy ``_find_layer`` to bridge the
# ``-`` vs ``_`` differences. Listing a name that isn't present is harmless.
ROLE_TARGETS: dict[str, list[tuple[str, str]]] = {
    "background": [("background", "background-color")],
    "water": [("water", "fill-color"), ("water-intermittent", "fill-color")],
    "waterway": [
        ("waterway", "line-color"),
        ("waterway-river", "line-color"),
        ("waterway-stream-canal", "line-color"),
        ("waterway-other", "line-color"),
    ],
    "land": [
        ("landuse_residential", "fill-color"),
        ("landuse_suburb", "fill-color"),
    ],
    "park": [
        ("landuse_park", "fill-color"),
        ("park", "fill-color"),
        ("landcover_wood", "fill-color"),
        ("landcover_grass", "fill-color"),
    ],
    "building": [("building", "fill-color")],
    "road_minor": [
        ("highway_minor", "line-color"),
        ("highway_path", "line-color"),
    ],
    "road_major": [
        ("highway_secondary_tertiary", "line-color"),
        ("highway_primary", "line-color"),
        ("highway_trunk", "line-color"),
        ("highway_major", "line-color"),
    ],
    "motorway": [
        ("highway_motorway", "line-color"),
        ("highway_motorway_link", "line-color"),
    ],
    "railway": [
        ("railway", "line-color"),
        ("railway_minor", "line-color"),
        ("railway_transit", "line-color"),
    ],
    "boundary": [
        ("boundary", "line-color"),
        ("boundary_state", "line-color"),
        ("boundary_country", "line-color"),
    ],
}

# Layout (symbol/placement) property names, used to decide paint vs layout.
LAYOUT_PROPS = {
    "visibility", "text-field", "text-font", "text-size", "text-anchor",
    "text-offset", "text-justify", "text-transform", "text-letter-spacing",
    "text-radial-offset", "text-variable-anchor", "icon-image", "icon-size",
    "icon-rotate", "icon-allow-overlap", "symbol-placement", "icon-opacity",
}


def normalize_prop(prop: str) -> str:
    """Map a model-provided property name to MapLibre's kebab-case form.

    Accepts kebab-case, snake_case (``fill_color``) and a couple of aliases
    (``color`` -> ``fill-color``).
    """
    if not prop:
        return prop
    p = str(prop).strip().replace("_", "-")
    aliases = {"color": "fill-color"}
    return aliases.get(p, p)


def _norm_id(layer_id: Any) -> str:
    """Canonical form of a layer id for fuzzy comparison (case/separators ignored)."""
    if layer_id is None:
        return ""
    return re.sub(r"[^a-z0-9]", "", str(layer_id).lower())


def _find_layer(style: dict[str, Any], layer_id: Any) -> dict[str, Any] | None:
    """Find a layer by id, tolerating case and ``-``/``_`` differences.

    OpenFreeMap styles are inconsistent about separators (e.g. ``highway-minor``
    vs ``highway_minor``) and models rarely know the exact spelling, so we first
    try an exact match and then a normalised one. Returns the layer dict or None.
    """
    if layer_id is None:
        return None
    layers = style.get("layers", [])
    for layer in layers:
        if layer.get("id") == layer_id:
            return layer
    target = _norm_id(layer_id)
    if not target:
        return None
    for layer in layers:
        if _norm_id(layer.get("id")) == target:
            return layer
    return None


def _suggest_layers(style: dict[str, Any], layer_id: Any, limit: int = 8) -> list[str]:
    """Rank the style's real layer ids by similarity to ``layer_id``."""
    ids = [l.get("id") for l in style.get("layers", []) if l.get("id")]
    if not ids:
        return []
    target = _norm_id(layer_id)
    q = str(layer_id or "").lower()
    tokens = [t for t in re.split(r"[^a-z0-9]+", q) if t]
    scored: list[tuple[float, str]] = []
    for i in ids:
        ni = _norm_id(i)
        ratio = difflib.SequenceMatcher(None, target, ni).ratio() if target else 0.0
        score = ratio
        li = i.lower()
        if q and q in li:
            score += 0.6
        if any(t in li for t in tokens if len(t) >= 3):
            score += 0.25
        scored.append((score, i))
    scored.sort(key=lambda x: (-x[0], x[1]))
    return [i for _, i in scored[:limit]]


def _layer_not_found(style: dict[str, Any], layer_id: Any) -> tuple[dict[str, Any], list]:
    """Standard error result when a layer id does not resolve.

    Crucially we hand the model the *real* ids (ranked guesses first) so it can
    pick a valid one on the very next call instead of guessing blindly.
    """
    return {
        "ok": False,
        "error": f"Layer '{layer_id}' was not found in the current style.",
        "hint": "Use one of the exact ids from 'didYouMean'/'layers', or call find_layers with keywords.",
        "didYouMean": _suggest_layers(style, layer_id),
        "layers": [l.get("id") for l in style.get("layers", []) if l.get("id")],
    }, []


def _short_json(obj: Any, limit: int = 160) -> str:
    """A compact single-line JSON string, truncated to keep context small."""
    s = json.dumps(obj, ensure_ascii=False)
    return s if len(s) <= limit else s[: max(0, limit - 3)] + "..."


def _layer_brief(layer: dict[str, Any]) -> dict[str, Any]:
    """A model-friendly summary of one layer (id, type, source, filter, label)."""
    lay = layer.get("layout") or {}
    b: dict[str, Any] = {
        "id": layer.get("id"),
        "type": layer.get("type"),
        "source-layer": layer.get("source-layer"),
        "visible": lay.get("visibility", "visible") != "none",
    }
    if layer.get("filter") is not None:
        b["filter"] = _short_json(layer["filter"])
    if lay.get("text-field") is not None:
        b["text-field"] = _short_json(lay["text-field"])
    if lay.get("icon-image"):
        b["icon-image"] = lay["icon-image"]
    return b


def _iter_text_layers(style: dict[str, Any]) -> list[dict[str, Any]]:
    """All symbol layers that render a text label."""
    out = []
    for layer in style.get("layers", []):
        if layer.get("type") == "symbol" and (layer.get("layout") or {}).get("text-field"):
            out.append(layer)
    return out


def apply_tokens(style: dict[str, Any], tokens: dict[str, Any]) -> list[dict[str, Any]]:
    """Apply a set of role tokens onto the style, returning map actions.

    Mutates ``style`` in place (server is the source of truth) and returns the
    granular paint actions the browser should apply to the live map.
    """
    actions: list[dict[str, Any]] = []

    for role, value in tokens.items():
        if role in ("label", "halo"):
            continue
        for layer_id, prop in ROLE_TARGETS.get(role, []):
            layer = _find_layer(style, layer_id)
            if layer is None:
                continue
            layer.setdefault("paint", {})[prop] = value
            actions.append({"type": "set_paint_property", "layer": layer_id,
                            "name": prop, "value": value})

    # Cohesive labelling across every text layer.
    text_color = tokens.get("label")
    halo_color = tokens.get("halo")
    for layer in _iter_text_layers(style):
        lid = layer.get("id")
        if text_color:
            layer.setdefault("paint", {})["text-color"] = text_color
            actions.append({"type": "set_paint_property", "layer": lid,
                            "name": "text-color", "value": text_color})
        if halo_color:
            layer.setdefault("paint", {})["text-halo-color"] = halo_color
            actions.append({"type": "set_paint_property", "layer": lid,
                            "name": "text-halo-color", "value": halo_color})

    return actions


# ---------------------------------------------------------------------------
# Tool executors
# ---------------------------------------------------------------------------
# Each tool is a function: (style, args) -> (result, actions). The server mutates
# ``style`` (source of truth) and returns granular ``actions`` for the browser.

def style_overview(style: dict[str, Any]) -> dict[str, Any]:
    """A compact, model-friendly description of the current style."""
    sources = {}
    for name, src in (style.get("sources") or {}).items():
        if isinstance(src, dict):
            sources[name] = {
                "type": src.get("type"),
                "tiles": src.get("tiles") or (src.get("url") and [src["url"]]),
            }
    layers = []
    for layer in style.get("layers", []):
        paint = layer.get("paint") or {}
        layout = layer.get("layout") or {}
        visible = layout.get("visibility", "visible") != "none"
        entry = {
            "id": layer.get("id"),
            "type": layer.get("type"),
            "source-layer": layer.get("source-layer"),
            "visible": visible,
        }
        if layer.get("filter") is not None:
            entry["filter"] = _short_json(layer["filter"], 80)
        # Surface the most useful paint props without bloating the context.
        keys = []
        for k in ("background-color", "fill-color", "line-color", "text-color", "icon-color",
                  "fill-opacity", "line-width", "text-size", "icon-opacity"):
            if k in paint:
                keys.append(k)
        if keys:
            entry["paint"] = {k: paint[k] for k in keys}
        layers.append(entry)
    return {
        "version": style.get("version"),
        "name": style.get("name"),
        "center": style.get("center"),
        "zoom": style.get("zoom"),
        "sources": sources,
        "layerCount": len(layers),
        "labelLayers": [
            l.get("id") for l in style.get("layers", [])
            if l.get("type") == "symbol" and (l.get("layout") or {}).get("text-field")
        ],
        "layers": layers,
        "paletteHint": "Use apply_palette for whole-map theming, update_layer/set_paint for specifics.",
        "discoverHint": "Call find_layers with keywords (e.g. 'road name label') to get exact layer ids before editing.",
    }


def _palettes_summary() -> list[dict[str, Any]]:
    out = []
    for name, pal in PALETTES.items():
        t = pal["tokens"]
        out.append({
            "name": name,
            "label": pal["label"],
            "mode": pal.get("mode"),
            "description": pal.get("description"),
            "swatches": [t.get("water"), t.get("park"), t.get("building"),
                         t.get("road_major"), t.get("motorway"), t.get("background")],
        })
    return out


def tool_get_style_overview(style, args):
    return {"ok": True, **style_overview(style)}, []


def tool_list_presets(style, args):
    return {
        "ok": True,
        "baseStyles": settings.BASE_STYLES,
        "note": "baseStyles are full MapLibre styles (load_preset); palettes recolour the current style (apply_palette).",
        "palettes": _palettes_summary(),
    }, []


def tool_get_preset(style, args):
    name = (args or {}).get("name")
    if name in PALETTES:
        pal = PALETTES[name]
        return {"ok": True, "kind": "palette", "name": name, "label": pal["label"],
                "description": pal.get("description"), "tokens": pal["tokens"]}, []
    if name in settings.BASE_STYLES:
        return {"ok": True, "kind": "baseStyle", "name": name,
                "description": "A full OpenFreeMap base style. Load it with load_preset."}, []
    return {"ok": False, "error": f"Unknown preset '{name}'.", "available":
            settings.BASE_STYLES + list(PALETTES.keys())}, []


def tool_load_preset(style, args):
    name = (args or {}).get("name")
    if name not in settings.BASE_STYLES:
        return {"ok": False, "error": f"'{name}' is not a base style.",
                "baseStyles": settings.BASE_STYLES}, []
    new = styles.resolve_style(name, settings.TILE_BASE_URL)
    new["name"] = f"earthiq:{name}"
    style.clear()
    style.update(new)
    return {"ok": True, "loaded": name, "layers": len(style.get("layers", []))}, \
        [{"type": "set_style", "style": json.loads(json.dumps(style))}]


def tool_apply_palette(style, args):
    name = (args or {}).get("name")
    if name not in PALETTES:
        return {"ok": False, "error": f"Unknown palette '{name}'.",
                "available": list(PALETTES.keys())}, []
    actions = apply_tokens(style, PALETTES[name]["tokens"])
    return {"ok": True, "palette": PALETTES[name]["label"],
            "appliedProps": len(actions),
            "swatches": _palettes_summary()[[p["name"] for p in _palettes_summary()].index(name)]["swatches"]}, \
        actions


def _visible_flag(v: Any) -> str:
    return "visible" if (v in (True, "true", "visible", 1, "1")) else "none"


def tool_update_layer(style, args):
    layer_id = (args or {}).get("layer_id")
    layer = _find_layer(style, layer_id)
    if layer is None:
        return _layer_not_found(style, layer_id)
    actions: list[dict[str, Any]] = []
    applied: list[str] = []

    paint = (args or {}).get("paint") or {}
    for prop, value in paint.items():
        np = normalize_prop(prop)
        layer.setdefault("paint", {})[np] = value
        actions.append({"type": "set_paint_property", "layer": layer_id, "name": np, "value": value})
        applied.append(f"paint.{np}")

    layout = (args or {}).get("layout") or {}
    for prop, value in layout.items():
        np = normalize_prop(prop)
        layer.setdefault("layout", {})[np] = value
        actions.append({"type": "set_layout_property", "layer": layer_id, "name": np, "value": value})
        applied.append(f"layout.{np}")

    if "filter" in (args or {}) and (args["filter"] is not None):
        layer["filter"] = args["filter"]
        actions.append({"type": "set_filter", "layer": layer_id, "filter": args["filter"]})
        applied.append("filter")

    if (args or {}).get("visible") is not None:
        layer.setdefault("layout", {})["visibility"] = _visible_flag(args["visible"])
        actions.append({"type": "set_visibility", "layer": layer_id, "visible": bool(args["visible"])})
        applied.append("visibility")

    return {"ok": True, "layer": layer_id, "applied": applied}, actions


def tool_set_paint(style, args):
    layer_id, prop, value = (args or {}).get("layer_id"), (args or {}).get("prop"), (args or {}).get("value")
    layer = _find_layer(style, layer_id)
    if layer is None:
        return _layer_not_found(style, layer_id)
    np = normalize_prop(prop)
    layer.setdefault("paint", {})[np] = value
    return {"ok": True, "layer": layer_id, "prop": np, "value": value}, \
        [{"type": "set_paint_property", "layer": layer_id, "name": np, "value": value}]


def tool_set_layout(style, args):
    layer_id, prop, value = (args or {}).get("layer_id"), (args or {}).get("prop"), (args or {}).get("value")
    layer = _find_layer(style, layer_id)
    if layer is None:
        return _layer_not_found(style, layer_id)
    np = normalize_prop(prop)
    layer.setdefault("layout", {})[np] = value
    return {"ok": True, "layer": layer_id, "prop": np, "value": value}, \
        [{"type": "set_layout_property", "layer": layer_id, "name": np, "value": value}]


def tool_set_visibility(style, args):
    layer_id = (args or {}).get("layer_id")
    layer = _find_layer(style, layer_id)
    if layer is None:
        return _layer_not_found(style, layer_id)
    visible = (args or {}).get("visible", True)
    layer.setdefault("layout", {})["visibility"] = _visible_flag(visible)
    return {"ok": True, "layer": layer_id, "visible": bool(visible)}, \
        [{"type": "set_visibility", "layer": layer_id, "visible": bool(visible)}]


def tool_set_background(style, args):
    color = (args or {}).get("color")
    if not color:
        return {"ok": False, "error": "color is required."}, []
    layer = _find_layer(style, "background")
    if layer is not None:
        layer.setdefault("paint", {})["background-color"] = color
    style["background"] = {"color": color}
    return {"ok": True, "background": color}, [{"type": "set_background", "color": color}]


def tool_set_config(style, args):
    args = args or {}
    view: dict[str, Any] = {}
    mapping = {
        "center": "center", "zoom": "zoom", "minzoom": "minzoom",
        "maxzoom": "maxzoom", "pitch": "pitch", "bearing": "bearing",
    }
    for key, field in mapping.items():
        if key in args and args[key] is not None:
            style[field] = args[key]
            view[field] = args[key]
    return {"ok": True, "view": view}, (
        [{"type": "set_config", "view": view}] if view else []
    )


def tool_add_layer(style, args):
    layer = (args or {}).get("layer") or {}
    if not layer.get("id") or not layer.get("type"):
        return {"ok": False, "error": "layer must include 'id' and 'type'."}, []
    if _find_layer(style, layer["id"]) is not None:
        return {"ok": False, "error": f"Layer '{layer['id']}' already exists."}, []
    layer.setdefault("source", "openmaptiles")
    style.setdefault("layers", []).append(layer)
    return {"ok": True, "added": layer["id"]}, [{"type": "set_style", "style": json.loads(json.dumps(style))}]


def tool_remove_layer(style, args):
    layer_id = (args or {}).get("layer_id")
    layer = _find_layer(style, layer_id)
    if layer is None:
        return _layer_not_found(style, layer_id)
    real_id = layer.get("id")
    style["layers"] = [l for l in style.get("layers", []) if l.get("id") != real_id]
    return {"ok": True, "removed": real_id}, [{"type": "set_style", "style": json.loads(json.dumps(style))}]


def tool_move_layer(style, args):
    layer_id = (args or {}).get("layer_id")
    layer = _find_layer(style, layer_id)
    if layer is None:
        return _layer_not_found(style, layer_id)
    index = (args or {}).get("index")
    layers = style.get("layers", [])
    idx = layers.index(layer)
    layers.pop(idx)
    target = 0 if index is None else max(0, min(int(index), len(layers)))
    layers.insert(target, layer)
    return {"ok": True, "moved": layer.get("id"), "index": target}, \
        [{"type": "set_style", "style": json.loads(json.dumps(style))}]


# Concept synonyms used by find_layers so a query like "road name label" also
# matches highway/street layers, and "city name" matches the place labels.
_SYNONYMS = {
    "road": ["highway", "street", "path", "route"],
    "highway": ["road", "street", "path"],
    "street": ["road", "highway"],
    "name": ["label", "text"],
    "label": ["name", "text"],
    "text": ["name", "label"],
    "city": ["place", "town", "village"],
    "place": ["city", "town", "village"],
    "town": ["city", "village", "place"],
    "village": ["city", "town", "place"],
    "water": ["river", "lake", "stream", "sea"],
    "river": ["water", "stream"],
    "railway": ["train", "rail", "transit"],
    "train": ["railway", "rail", "transit"],
    "boundary": ["border", "state", "country"],
    "country": ["boundary", "state", "border"],
    "state": ["boundary", "country"],
}


def _expand_tokens(tokens: list[str]) -> list[str]:
    """Expand each query token with its synonyms and de-pluralised form.

    Handles the common case where the user/model says a plural ("rivers",
    "buildings", "roads") but the layer ids are singular ("river", "building",
    "road"). De-duplicated, order preserved.
    """
    out: list[str] = []
    seen: set[str] = set()

    def add(cand: str) -> None:
        if cand and cand not in seen:
            seen.add(cand)
            out.append(cand)

    for t in tokens:
        forms = [t]
        if t.endswith("s") and len(t) > 3:
            forms.append(t[:-1])
        for base in forms:
            add(base)
            for s in _SYNONYMS.get(base, []):
                add(s)
    return out


def tool_find_layers(style, args):
    """Find layers by keyword, returning their exact ids + semantics.

    This is the model's primary way to *discover* the real layer id for a
    concept ("road name label", "city name", "rivers") without guessing. It
    scores every layer by how many of the query keywords appear across its id,
    source-layer, filter and text-field, so the best matches (with the exact id
    to pass to update_layer / set_visibility) come back first.
    """
    args = args or {}
    query = str(args.get("query") or "").strip()
    kind = str(args.get("kind") or "").strip().lower()
    src = str(args.get("source_layer") or "").strip()
    tokens = [t for t in re.split(r"[^a-z0-9]+", query.lower()) if t]
    if not tokens:
        return {"ok": False, "error": "Provide a 'query' with at least one keyword (e.g. 'road name label').",
                "layers": [l.get("id") for l in style.get("layers", []) if l.get("id")]}, []

    expanded = _expand_tokens(tokens)

    def _hits(text: str) -> int:
        return sum(1 for t in expanded if t and t in text)

    scored: list[tuple[float, dict[str, Any]]] = []
    for layer in style.get("layers", []):
        if not layer.get("id"):
            continue
        if kind and layer.get("type") != kind:
            continue
        if src and _norm_id(layer.get("source-layer")) != _norm_id(src):
            continue
        lid = str(layer.get("id") or "").lower()
        sly = str(layer.get("source-layer") or "").lower()
        filt = json.dumps(layer.get("filter") or "").lower()
        tf = json.dumps((layer.get("layout") or {}).get("text-field") or "").lower()
        icon = json.dumps((layer.get("layout") or {}).get("icon-image") or "").lower()
        # Weight the layer id most (it's the most meaningful signal), the
        # source-layer next, and the (boilerplate) text-field least.
        score = (
            _hits(lid) * 3.0
            + _hits(sly) * 2.0
            + _hits(filt) * 1.0
            + _hits(icon) * 1.0
            + _hits(tf) * 0.4
        )
        if score <= 0:
            continue
        if query.lower() in lid:
            score += 2.0
        scored.append((score, layer))

    scored.sort(key=lambda x: (-x[0], x[1].get("id") or ""))
    top = scored[:12]
    result: dict[str, Any] = {
        "ok": True,
        "query": query,
        "count": len(top),
        "matches": [_layer_brief(l) for _, l in top],
    }
    if not top:
        labels = [
            _layer_brief(l) for l in style.get("layers", [])
            if l.get("type") == "symbol" and (l.get("layout") or {}).get("text-field")
        ]
        result.update({
            "noMatch": True,
            "hint": "No layer matched those keywords. Try a single, broader keyword, or hide these label layers:",
            "labelLayers": labels[:20],
            "layers": [l.get("id") for l in style.get("layers", []) if l.get("id")],
        })
    return result, []


# ---------------------------------------------------------------------------
# Dispatch + tool schemas
# ---------------------------------------------------------------------------
TOOL_FNS = {
    "get_style_overview": tool_get_style_overview,
    "list_presets": tool_list_presets,
    "get_preset": tool_get_preset,
    "load_preset": tool_load_preset,
    "apply_palette": tool_apply_palette,
    "update_layer": tool_update_layer,
    "set_paint": tool_set_paint,
    "set_layout": tool_set_layout,
    "set_visibility": tool_set_visibility,
    "set_background": tool_set_background,
    "set_config": tool_set_config,
    "add_layer": tool_add_layer,
    "remove_layer": tool_remove_layer,
    "move_layer": tool_move_layer,
    "find_layers": tool_find_layers,
}


def execute_tool(style: dict[str, Any], name: str, args: dict | None):
    """Run a tool by name, returning (result, actions). Never raises."""
    fn = TOOL_FNS.get(name)
    if fn is None:
        return {"ok": False, "error": f"Unknown tool '{name}'.",
                "tools": list(TOOL_FNS)}, []
    try:
        return fn(style, args or {})
    except Exception as exc:  # defensive: keep the agent loop alive
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}, []


def _obj(properties: dict, required=None) -> dict:
    return {"type": "object", "properties": properties, "required": required or []}


TOOLS = [
    {"type": "function", "function": {
        "name": "get_style_overview",
        "description": "Inspect the current map: sources, layer ids/types/visibility and key paint props. Call this first when unsure which layers exist.",
        "parameters": _obj({})}},
    {"type": "function", "function": {
        "name": "find_layers",
        "description": "Search the current style's layers by keyword and return the best matches with their EXACT ids, source-layer, filter and text-field. Use this to discover the real id of a concept (e.g. 'road name label', 'city name', 'river', 'building') before editing - never guess an id.",
        "parameters": _obj({
            "query": {"type": "string", "description": "Keywords describing the layer, e.g. 'road name label' or 'city place name'."},
            "kind": {"type": "string", "description": "Optional MapLibre layer type: symbol, line, fill, circle, background, raster."},
            "source_layer": {"type": "string", "description": "Optional vector source-layer name (e.g. transportation_name, place)."},
        }, ["query"])}},
    {"type": "function", "function": {
        "name": "list_presets",
        "description": "List available base styles and colour palettes with descriptions.",
        "parameters": _obj({})}},
    {"type": "function", "function": {
        "name": "get_preset",
        "description": "Get details (colours/tokens) of a palette or base style by name.",
        "parameters": _obj({"name": {"type": "string"}}, ["name"])}},
    {"type": "function", "function": {
        "name": "load_preset",
        "description": "Load a full base style (replaces the current design). Use for switching the whole base map.",
        "parameters": _obj({"name": {"type": "string"}}, ["name"])}},
    {"type": "function", "function": {
        "name": "apply_palette",
        "description": "Recolour the whole map cohesively (water, land, parks, buildings, roads, rails, labels, background) using a named palette. Best for 'make it a <theme> map' requests.",
        "parameters": _obj({"name": {"type": "string"}}, ["name"])}},
    {"type": "function", "function": {
        "name": "update_layer",
        "description": "Edit one layer: set paint and/or layout properties, a filter, and/or visibility. Properties accept kebab or snake case (fill-color, line-width, text-size...).",
        "parameters": _obj({
            "layer_id": {"type": "string"},
            "paint": {"type": "object", "description": "e.g. {\"fill-color\":\"#336699\",\"line-width\":3}"},
            "layout": {"type": "object"},
            "filter": {"type": "array", "description": "MapLibre filter expression"},
            "visible": {"type": "boolean"},
        }, ["layer_id"])}},
    {"type": "function", "function": {
        "name": "set_paint",
        "description": "Set a single paint property on a layer.",
        "parameters": _obj({
            "layer_id": {"type": "string"},
            "prop": {"type": "string", "description": "e.g. fill-color, line-color, text-color, line-width"},
            "value": {},
        }, ["layer_id", "prop", "value"])}},
    {"type": "function", "function": {
        "name": "set_layout",
        "description": "Set a single layout property on a layer (e.g. text-size, visibility).",
        "parameters": _obj({
            "layer_id": {"type": "string"}, "prop": {"type": "string"}, "value": {},
        }, ["layer_id", "prop", "value"])}},
]

TOOLS.extend(
    [
        {"type": "function", "function": {
            "name": "set_visibility",
            "description": "Show or hide a layer.",
            "parameters": _obj({
                "layer_id": {"type": "string"}, "visible": {"type": "boolean"},
            }, ["layer_id", "visible"])}},
        {"type": "function", "function": {
            "name": "set_background",
            "description": "Set the map background colour.",
            "parameters": _obj({"color": {"type": "string"}}, ["color"])}},
        {"type": "function", "function": {
            "name": "set_config",
            "description": "Set camera/config: center [lng,lat], zoom, minzoom, maxzoom, pitch, bearing.",
            "parameters": _obj({
                "center": {"type": "array", "items": {"type": "number"}},
                "zoom": {"type": "number"}, "minzoom": {"type": "number"},
                "maxzoom": {"type": "number"}, "pitch": {"type": "number"},
                "bearing": {"type": "number"},
            })}},
        {"type": "function", "function": {
            "name": "add_layer",
            "description": "Add a brand-new layer (fill/line/symbol/background) on top of the current style.",
            "parameters": _obj({"layer": {"type": "object"}}, ["layer"])}},
        {"type": "function", "function": {
            "name": "remove_layer",
            "description": "Remove a layer by id.",
            "parameters": _obj({"layer_id": {"type": "string"}}, ["layer_id"])}},
        {"type": "function", "function": {
            "name": "move_layer",
            "description": "Reorder a layer to a new index in the style's layer array (0 = bottom).",
            "parameters": _obj({
                "layer_id": {"type": "string"}, "index": {"type": "integer"},
            }, ["layer_id"])}},
    ]
)


SYSTEM_PROMPT = """You are EarthIQ, an expert cartographer and base-map design assistant.

The design target is a live MapLibre GL style rendered on OpenFreeMap vector
tiles (OpenStreetMap / OpenMapTiles schema). You change the design by calling
the provided tools; the browser applies each change to the live map.

Rules of thumb:
- NEVER guess a layer id. Before you edit, hide or recolour a layer, discover its
  EXACT id: call find_layers with keywords that describe it (e.g. "road name
  label", "city name", "river", "building") and use the id from the matches. If
  find_layers is unavailable, call get_style_overview and read the real ids there.
- If any tool returns ok=false / "not found", do NOT retry with a guessed id.
  Read its "didYouMean" and "layers" lists and call the tool again with one of
  those exact ids.
- A concept can map to SEVERAL layers (e.g. road names are often
  highway-name-major / highway-name-minor / highway-name-path). Apply the same
  change to every matching layer, not just one.
- For a whole-map mood or theme ("warm desert", "night mode", "minimal light",
  "pastel", "ocean"), prefer apply_palette with a matching palette name, then
  tweak individual layers if needed.
- For specific edits use update_layer / set_paint / set_layout / set_visibility.
- Keep labels legible: set a readable text-color and a contrasting text-halo-color.
- Property names are MapLibre kebab-case: fill-color, line-color, line-width,
  text-color, text-halo-color, text-size, fill-opacity, line-opacity, icon-opacity.
  (You may write snake_case; it is normalised for you.)
- Prefer small, deliberate changes. Do a few tools, then stop.
- If you are unable to call a tool, write the action as its own line in exactly
  this format and nothing else:  ACTION: apply_palette name=desert
- When you are done, reply with ONE short sentence describing what you changed.
  Do not call more tools after describing the result.

Available base styles: {base_styles}.
Available palettes: {palettes}.
"""
