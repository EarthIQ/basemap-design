# ◈ EarthIQ · AI base map designer

An **AI-powered base map designer**. Describe the map you want in plain English and
an LLM agent edits a live **MapLibre GL style** for you, recolouring the whole map
with curated palettes, tweaking individual layers, toggling visibility, adjusting
road/label styling, and more. You can also design by hand in the Inspector.

Vector data comes from **[OpenFreeMap](https://openfreemap.org)** (OpenStreetMap /
Planetiler, free and keyless). The AI works with **Ollama (local)** out of the box and
with any **OpenAI-compatible** endpoint (OpenAI, OpenRouter, Groq, Together,
LM Studio, …).

```
 ┌────────────┐   tools   ┌─────────────┐   style JSON   ┌───────────────────┐
 │ You (chat) │ ────────▶ │EarthIQ agent│ ──────────────▶ │ MapLibre GL (live)│
 └────────────┘           │  (LLM)      │ ◀────────────── └───────────────────┘
                          └─────────────┘   OpenFreeMap vector tiles (.pbf)
```

## What it does

- **Natural-language design**: “warm desert map”, “calm ocean theme”, “night mode”,
  “thicker highways”, “hide labels”. The agent picks the right tools and applies them
  live, so you watch the map change as it works.
- **Whole-map theming**: 12 curated, cohesive palettes (Ocean, Desert, Forest,
  Midnight, Neon, Pastel, Vintage, …) applied in one step across water, land, parks,
  buildings, roads, rails and labels.
- **Five base maps**: bright, dark, fiord, liberty, positron (full OpenFreeMap styles).
- **Manual Inspector**: toggle any layer, recolor it, tune widths/opacities/label size.
- **Export & import**: copy/download the style JSON, copy a MapLibre embed, or import a previously exported .json.
- **Self-hosting**: point the tile base URL at your own OpenFreeMap deployment.
- **Local-first AI**: runs fully offline with a local Ollama model.

## Architecture

- **Backend**: Python 3.12 + FastAPI + httpx. Holds the style as the single source of
  truth, runs the LLM tool-calling loop, and streams progress over Server-Sent Events.
- **Design engine** (`server/design.py`): the tool set + curated palettes. The same
  functions back both the AI agent and the manual Inspector, so the server and the map
  never drift.
- **LLM adapters** (`server/llm.py`): Ollama (`/api/chat`, NDJSON streaming + tool calls)
  and OpenAI-compatible (`/chat/completions` + tools), behind one streaming interface
  that yields text token-by-token.
- **Frontend** (`frontend/`): a React 19 + Vite single-page app styled with
  **Tailwind CSS v4** and **lucide-react** icons, rendering the live map with
  **MapLibre GL**. Assistant replies stream in token-by-token and every tool call
  is shown as a live status chip, so you can see exactly what the agent is doing.

### Project layout
```
server/
  main.py       FastAPI app: routes, SSE chat, static SPA, session state
  agent.py      tool-calling loop that yields streamable events (incl. token deltas)
  design.py     palettes + style tools (executors, schemas, system prompt)
  llm.py        Ollama + OpenAI-compatible streaming adapters + model listing
  styles.py     fetch/cache/resolve OpenFreeMap styles (domain substitution)
  settings.py   defaults & runtime configuration
frontend/
  index.html    Vite entry
  vite.config.js  Vite + React + Tailwind v4 plugins, dev /api proxy
  src/
    main.jsx        React entry
    App.jsx         app shell: state, map, provider/model, tab routing
    index.css       Tailwind v4 theme + MapLibre control theming
    lib/            api + SSE client, MapLibre helpers, utils
    state/          Toast context
    components/     Header, SettingsPanel, MapView, Sidebar, QuickPrompts
      chat/         AITab (streaming chat) + Turn (live block timeline)
      tabs/         Palettes, Inspector, Export
    dist/           built app (gitignored; produced by `npm run build`)
data/styles/    cached OpenFreeMap style JSONs (auto-filled on first run)
run.sh          one-command launcher (builds the frontend on demand)
```

## Requirements

- **Python 3.12** and **uv** (for dependency management)
- **Node.js 20+** and **npm** (to build the React frontend)
- **Ollama** running locally (for the local AI): e.g. `ollama serve` with a
  tool-calling model pulled. Any model that supports tool calling works; smaller
  models are fine for simple asks, a 7B+ model (e.g. `qwen2.5:7b`, `llama3.1:8b`)
  gives the most reliable results.
- An internet connection on first run (to fetch the OpenFreeMap styles + tiles), or
  point it at a self-hosted OpenFreeMap instance.

## Run it

```bash
cd basemaps
./run.sh                 # builds the frontend if needed → http://127.0.0.1:8000
./run.sh --dev           # dev: Vite hot-reload on :5173 + API on :8000
# or manually:
uv venv --python 3.12 .venv
uv pip install -r requirements.txt --python .venv/bin/python
cd frontend && npm install && npm run build && cd ..
.venv/bin/python -m uvicorn server.main:app --host 127.0.0.1 --port 8000
```

Open **http://127.0.0.1:8000**. Pick the base map and engine up top, then start
describing the map you want in the **AI** tab. In development, use
**http://127.0.0.1:5173** (the Vite dev server proxies `/api` to the backend).

## Using it

1. **AI tab**: type a request, or click a quick chip. Watch the agent’s tool calls
   stream in (each one updates the live map as it happens).
2. **Palettes tab**: one-click cohesive themes, or switch the base style.
3. **Inspector tab**: fine control per layer: visibility 👁, colour, opacity, width,
   label size, plus quick swatches.
4. **Export tab**: copy/download the MapLibre style JSON, copy an embed snippet, or import a .json.

## AI tools (what the model can do)

| Tool | Purpose |
| --- | --- |
| `get_style_overview` | Inspect sources, layer ids/types, key paint props |
| `list_presets` / `get_preset` | Discover base styles & palettes |
| `load_preset` | Switch the whole base map |
| `apply_palette` | Recolour the entire map cohesively |
| `update_layer` | Set paint/layout props, filter, visibility on one layer |
| `set_paint` / `set_layout` | Set a single property |
| `set_visibility` | Show/hide a layer |
| `set_background` | Set the map background colour |
| `set_config` | Camera: center/zoom/minzoom/maxzoom/pitch/bearing |
| `add_layer` / `remove_layer` / `move_layer` | Structural layer edits |

Property names are normalised, so the model can write `fill_color` or `fill-color`.

## Configuration

All runtime settings are changeable in the UI (⚙) and via env vars:

| Env var | Default | Meaning |
| --- | --- | --- |
| `EARTHIQ_TILE_BASE_URL` | `https://tiles.openfreemap.org` | Tile/style host (self-host here) |
| `OLLAMA_BASE_URL` | `http://localhost:11444` | Ollama server |
| `EARTHIQ_OLLAMA_MODEL` | `qwen3.8:27b` | Default Ollama model |
| `OPENAI_BASE_URL` / `OPENAI_API_KEY` / `OPENAI_MODEL` | OpenRouter defaults | OpenAI-compatible endpoint |
| `EARTHIQ_MAX_STEPS` | `8` | Max tool steps per turn |

### Self-hosting tiles

If you run your own [OpenFreeMap](https://github.com/hyperknot/openfreemap), set the
**Tile base URL** in ⚙ Settings to your domain (e.g. `https://tiles.example.com`).
EarthIQ re-points the sprite/glyph/source URLs automatically.

### The OpenFreeMap endpoints used

- Vector (TileJSON): `https://tiles.openfreemap.org/planet`
- MVT tiles: `https://tiles.openfreemap.org/planet/{z}/{x}/{y}.pbf`
- Natural Earth raster: `https://tiles.openfreemap.org/natural_earth/ne2sr/{z}/{x}/{y}.png`
- Sprites: `https://tiles.openfreemap.org/sprites/ofm_f384/ofm`
- Glyphs: `https://tiles.openfreemap.org/fonts/{fontstack}/{range}.pbf`

## HTTP API (for scripting)

| Method & path | Description |
| --- | --- |
| `GET /api/health` | Server + Ollama status, endpoints, models |
| `GET/POST /api/settings` | Read / update provider & tile config |
| `GET /api/models?provider=` | List models for a provider (model picker) |
| `GET /api/styles` | Base style metadata |
| `GET /api/palettes` | Palette list + swatches |
| `POST /api/session/load` `{name}` | Load a base style |
| `POST /api/session/import` `{style}` | Import a previously-exported style JSON |
| `GET /api/session/style` / `overview` | Current style / compact overview |
| `POST /api/apply` `{name,args}` | Run one design tool (Inspector) |
| `POST /api/chat` `{message}` | Run the agent (SSE stream) |

## Notes & limitations

- Single-user, in-memory session state (resets on server restart). Add persistence if
  you need saved designs.
- The design object is the MapLibre style; tile *data* is always OpenFreeMap/OSM.
- Attribution is required for OSM/OpenFreeMap data when distributing (MapLibre shows it
  automatically in the map control).

## License & attribution

EarthIQ is MIT. Map data © OpenStreetMap contributors; tiles & styles © OpenFreeMap
(© OpenMapTiles). When using in print/video, include:
`OpenFreeMap © OpenMapTiles · Data from OpenStreetMap`.