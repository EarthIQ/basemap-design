import { useEffect, useRef } from "react";
import { Map as MapIcon } from "lucide-react";
import { createMap } from "../lib/maplibre";
import QuickPrompts from "./QuickPrompts.jsx";

/**
 * Owns the MapLibre map instance for the lifetime of the component.
 * `initialStyle` must be non-null on first mount (App gates rendering on load).
 */
export default function MapView({ initialStyle, onMap, styleName, onQuick }) {
  const containerRef = useRef(null);
  const mapRef = useRef(null);

  useEffect(() => {
    if (!containerRef.current || !initialStyle) return;
    const map = createMap(containerRef.current, initialStyle);
    mapRef.current = map;
    onMap?.(map);
    return () => {
      map.remove();
      mapRef.current = null;
    };
    // Create the map exactly once.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="relative min-h-0 min-w-0 flex-1">
      <div ref={containerRef} className="absolute inset-0 h-full w-full" />

      {/* Current style badge */}
      <div className="pointer-events-none absolute left-3 top-3 z-[5] flex items-center gap-2 rounded-lg border border-line bg-ink-900/80 px-3 py-1.5 text-xs text-ink-300 backdrop-blur">
        <MapIcon size={14} className="text-glow" />
        <span className="max-w-[180px] truncate font-medium text-ink-200">
          {styleName || "…"}
        </span>
      </div>

      <QuickPrompts onQuick={onQuick} />
    </div>
  );
}
