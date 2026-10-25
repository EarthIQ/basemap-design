/**
 * Shared API / map types for the EarthIQ Basemap frontend.
 *
 * MapLibre style objects are dynamic (layers/props vary per style), so we use
 * loose structural types here rather than the full maplibre-gl schema.
 */

/* ----------------------------------------------------------------- styles --- */
export type MapStyle = Record<string, unknown> & {
  name?: string;
  version?: number;
  center?: [number, number];
  zoom?: number;
  layers?: MapLayer[];
  sources?: Record<string, unknown>;
};

export type MapLayer = {
  id?: string;
  type?: string;
  "source-layer"?: string;
  visible?: boolean;
  filter?: unknown;
  paint?: Record<string, unknown>;
  layout?: Record<string, unknown>;
} & Record<string, unknown>;

export type Overview = {
  version?: number;
  name?: string;
  center?: [number, number];
  zoom?: number;
  sources?: Record<string, { type?: string; tiles?: string[] }>;
  layerCount?: number;
  labelLayers?: string[];
  layers?: MapLayer[];
};

export type Palette = {
  name: string;
  label: string;
  mode?: string;
  description?: string;
  swatches?: (string | null)[];
};

export type Settings = {
  provider?: string;
  ollama?: { baseUrl?: string; model?: string };
  openai?: { baseUrl?: string; model?: string; hasKey?: boolean };
  tileBaseUrl?: string;
  baseStyles?: string[];
};

export type Health = {
  ok?: boolean;
  ollama?: { ok?: boolean; baseUrl?: string; version?: string; models?: string[] };
  tileBaseUrl?: string;
  provider?: string;
  model?: string;
  baseStyles?: string[];
  endpoints?: Record<string, string>;
};

/* ------------------------------------------------------------------- maps --- */
/** A granular map action the backend returns for the browser to apply. */
export type MapAction = {
  type: string;
  layer?: string;
  name?: string;
  value?: unknown;
  filter?: unknown;
  visible?: boolean;
  color?: string;
  view?: Record<string, unknown>;
  style?: MapStyle;
} & Record<string, unknown>;

export type ToolResult = Record<string, unknown>;

export type TabId = "ai" | "palettes" | "inspector" | "export";

/* ------------------------------------------------------------------ chat --- */
export type SSEEvent =
  | { type: "start"; model?: string; provider?: string }
  | { type: "thinking"; note?: string }
  | { type: "assistant_delta"; content: string }
  | { type: "assistant"; content: string }
  | { type: "tool_call"; name: string; arguments: Record<string, unknown> }
  | { type: "tool_result"; name: string; result: ToolResult; actions: MapAction[] }
  | { type: "error"; message: string }
  | { type: "done"; overview?: Overview; style?: MapStyle };

export type TurnPart =
  | { id: string; kind: "thinking"; note?: string }
  | { id: string; kind: "text"; content: string }
  | {
      id: string;
      kind: "tool";
      name: string;
      args: Record<string, unknown>;
      status: "running" | "done" | "fail";
      result?: ToolResult;
    }
  | { id: string; kind: "error"; message: string };

export type Turn = {
  id: string;
  role: "user" | "assistant";
  text?: string;
  status?: "running" | "done" | "error";
  parts?: TurnPart[];
};
