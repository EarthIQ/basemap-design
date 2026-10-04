import {
  Map as MapLibreMap,
  NavigationControl,
  ScaleControl,
  setWorkerUrl,
} from "maplibre-gl";
import "maplibre-gl/dist/maplibre-gl.css";
// Vite bundles MapLibre's render worker as a standalone file and hands back its
// URL. We must point MapLibre at it explicitly: by default MapLibre resolves
// the worker relative to `import.meta.url`, which in a Vite build is the app
// bundle, so it 404s the worker and the canvas renders blank.
import maplibreWorkerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url";

setWorkerUrl(maplibreWorkerUrl);

/**
 * Create a MapLibre GL map bound to `container`, preloaded with `style`.
 * Returns the map instance (call `.remove()` on unmount).
 */
export function createMap(container, style) {
  const map = new MapLibreMap({
    container,
    style,
    // Backend styles omit the camera; give a sensible default so the map never
    // boots to a blank full-world view.
    center: style?.center ?? [10, 22],
    zoom: style?.zoom ?? 2,
    attributionControl: { compact: true },
  });

  map.addControl(new NavigationControl({ showCompass: false }), "top-right");
  map.addControl(new ScaleControl({ unit: "imperial" }), "bottom-left");
  return map;
}

/** Apply a single granular action to the live map. Never throws. */
export function applyOne(map, a) {
  if (!map) return;
  try {
    switch (a.type) {
      case "set_paint_property":
        if (map.getLayer(a.layer)) map.setPaintProperty(a.layer, a.name, a.value);
        break;
      case "set_layout_property":
        if (map.getLayer(a.layer)) map.setLayoutProperty(a.layer, a.name, a.value);
        break;
      case "set_filter":
        if (map.getLayer(a.layer)) map.setFilter(a.layer, a.filter);
        break;
      case "set_visibility":
        if (map.getLayer(a.layer))
          map.setLayoutProperty(a.layer, "visibility", a.visible ? "visible" : "none");
        break;
      case "set_background": {
        if (map.getLayer("background")) {
          const cur = map.getPaintProperty("background", "background-color");
          if (cur !== undefined) map.setPaintProperty("background", "background-color", a.color);
          else map.setPaintProperty("background", "fill-color", a.color);
        }
        break;
      }
      case "set_config": {
        const v = a.view || {};
        if (v.center && v.zoom != null) map.jumpTo({ center: v.center, zoom: v.zoom });
        else if (v.center) map.jumpTo({ center: v.center });
        else if (v.zoom != null) map.setZoom(v.zoom);
        if (v.pitch != null) map.setPitch(v.pitch);
        if (v.bearing != null) map.setBearing(v.bearing);
        break;
      }
      case "set_style":
        map.setStyle(a.style);
        break;
      default:
        break;
    }
  } catch (e) {
    console.warn("apply action failed:", a, e);
  }
}

/**
 * Apply a list of actions to the live map. A full `set_style` wipes the map and
 * re-tiles, so any action after it is deferred until the map is idle again.
 */
export function applyActions(map, actions) {
  if (!actions || !actions.length || !map) return;
  const deferred = [];
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
