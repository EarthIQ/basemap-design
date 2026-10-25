import { Map as MapLibreMap, NavigationControl, ScaleControl, setWorkerUrl } from "maplibre-gl";
import type { FilterSpecification, Map as MapType, MapOptions } from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
// Vite bundles MapLibre's render worker as a standalone file and hands back its
// URL. We must point MapLibre at it explicitly: by default MapLibre resolves
// the worker relative to `import.meta.url`, which in a Vite build is the app
// bundle, so it 404s the worker and the canvas renders blank.
import maplibreWorkerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url";
import type { MapAction, MapStyle } from "@/lib/types";

setWorkerUrl(maplibreWorkerUrl);

/**
 * Create a MapLibre GL map bound to `container`, preloaded with `style`.
 * Returns the map instance (call `.remove()` on unmount).
 */
export function createMap(container: HTMLElement, style: MapStyle | null): MapType {
  const map = new MapLibreMap({
    container,
    // Our styles are plain JSON from the backend, not maplibre's strict
    // schema, so hand it over with a cast.
    style: style as unknown as MapOptions["style"],
    // Backend styles omit the camera; give a sensible default so the map never
    // boots to a blank full-world view.
    center: (style?.center as [number, number] | undefined) ?? [10, 22],
    zoom: (style?.zoom as number | undefined) ?? 2,
    attributionControl: { compact: true },
  });

  map.addControl(new NavigationControl({ showCompass: false }), "top-right");
  map.addControl(new ScaleControl({ unit: "imperial" }), "bottom-left");
  return map;
}

/** Apply a single granular action to the live map. Never throws. */
export function applyOne(map: MapType | null, a: MapAction): void {
  if (!map) return;
  // Actions are dynamic (backend-generated); treat as loosely typed.
  const act = a as Record<string, any>;
  try {
    switch (act.type) {
      case "set_paint_property":
        if (map.getLayer(act.layer)) map.setPaintProperty(act.layer, act.name, act.value);
        break;
      case "set_layout_property":
        if (map.getLayer(act.layer)) map.setLayoutProperty(act.layer, act.name, act.value);
        break;
      case "set_filter":
        if (map.getLayer(act.layer)) map.setFilter(act.layer, act.filter as FilterSpecification);
        break;
      case "set_visibility":
        if (map.getLayer(act.layer))
          map.setLayoutProperty(act.layer, "visibility", act.visible ? "visible" : "none");
        break;
      case "set_background": {
        if (map.getLayer("background")) {
          const cur = map.getPaintProperty("background", "background-color");
          if (cur !== undefined) map.setPaintProperty("background", "background-color", act.color);
          else map.setPaintProperty("background", "fill-color", act.color);
        }
        break;
      }
      case "set_config": {
        const v = (act.view || {}) as Record<string, unknown>;
        if (v.center && v.zoom != null)
          map.jumpTo({ center: v.center as [number, number], zoom: v.zoom as number });
        else if (v.center) map.jumpTo({ center: v.center as [number, number] });
        else if (v.zoom != null) map.setZoom(v.zoom as number);
        if (v.pitch != null) map.setPitch(v.pitch as number);
        if (v.bearing != null) map.setBearing(v.bearing as number);
        break;
      }
      case "set_style":
        map.setStyle(act.style as Parameters<MapType["setStyle"]>[0]);
        break;
      default:
        break;
    }
  } catch (e) {
    console.warn("apply action failed:", act, e);
  }
}

/**
 * Apply a list of actions to the live map. A full `set_style` wipes the map and
 * re-tiles, so any action after it is deferred until the map is idle again.
 */
export function applyActions(map: MapType | null, actions: MapAction[] | null | undefined): void {
  if (!actions || !actions.length || !map) return;
  const deferred: MapAction[] = [];
  let styleLoading = false;
  for (const a of actions) {
    if (a.type === "set_style") {
      applyOne(map, a);
      styleLoading = true;
    } else if (styleLoading) {
      deferred.push(a);
    } else {
      applyOne(map, a);
    }
  }
  if (styleLoading && deferred.length) {
    map.once("idle", () => deferred.forEach((a) => applyOne(map, a)));
  }
}
