import { Eye, EyeOff, Layers, SlidersHorizontal, X } from "lucide-react";
import { cn, layerPropsFor, toHex } from "../../lib/utils";

const SWATCHES = ["#ffffff", "#111111", "#22d3ee", "#f0abfc", "#f0a92b", "#57cc77", "#e5484d"];

function LayerRow({ layer, selected, onSelect, onToggleVis }) {
  return (
    <div
      onClick={() => onSelect(layer.id)}
      className={cn(
        "flex cursor-pointer items-center gap-2.5 rounded-lg px-2.5 py-2 text-[13px] transition",
        selected ? "bg-brand-500/15 ring-1 ring-inset ring-brand-500/40" : "hover:bg-ink-800"
      )}
    >
      <button
        onClick={(e) => {
          e.stopPropagation();
          onToggleVis(layer.id, !layer.visible);
        }}
        title="Toggle visibility"
        className="grid h-6 w-6 shrink-0 place-items-center rounded-md text-ink-300 transition hover:bg-white/10 hover:text-ink-100"
      >
        {layer.visible ? <Eye size={15} /> : <EyeOff size={15} className="opacity-60" />}
      </button>
      <span className="flex-1 truncate font-mono text-xs text-ink-100">{layer.id}</span>
      <span className="shrink-0 rounded border border-line bg-ink-900 px-1.5 py-0.5 text-[10px] text-ink-300">
        {layer.type}
      </span>
    </div>
  );
}

function PropRow({ prop, kind, value, onChange }) {
  return (
    <div className="mb-2.5 flex items-center gap-2">
      <label className="flex-1 truncate font-mono text-[11px] text-ink-300">{prop}</label>
      {kind === "color" ? (
        <>
          <div className="flex items-center gap-1">
            {SWATCHES.map((c) => (
              <button
                key={c}
                title={c}
                onClick={() => onChange(c)}
                className="h-4 w-4 rounded border border-line"
                style={{ background: c }}
              />
            ))}
          </div>
          <input
            type="color"
            value={toHex(value)}
            onChange={(e) => onChange(e.target.value)}
            className="h-7 w-10 cursor-pointer"
          />
        </>
      ) : (
        <input
          type="number"
          step="0.5"
          value={value != null ? value : ""}
          onChange={(e) => {
            if (e.target.value === "") return;
            const n = Number(e.target.value);
            if (!Number.isNaN(n)) onChange(n);
          }}
          className="h-7 w-20 rounded-md border border-line bg-ink-850 px-2 text-xs text-ink-100 outline-none focus:border-brand-500"
        />
      )}
    </div>
  );
}

export default function InspectorTab({
  overview = { layers: [] },
  selectedLayer = null,
  onSelectLayer,
  onClearSelection,
  onToggleVis,
  onApplyProp,
}) {
  const layers = overview.layers || [];
  const selected = layers.find((l) => l.id === selectedLayer);

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="flex items-center gap-2 px-4 pb-2 pt-3 text-[11px] text-ink-500">
        <Layers size={14} />
        {layers.length} layers · click to edit · eye to toggle
      </div>

      <div className="min-h-0 flex-1 space-y-0.5 overflow-y-auto px-3 pb-2">
        {layers.map((l) => (
          <LayerRow
            key={l.id}
            layer={l}
            selected={l.id === selectedLayer}
            onSelect={onSelectLayer}
            onToggleVis={onToggleVis}
          />
        ))}
        {layers.length === 0 && (
          <p className="px-2 py-4 text-sm text-ink-300">No layers to inspect.</p>
        )}
      </div>

      {selected && (
        <div className="animate-fade-in border-t border-line p-3">
          <div className="mb-3 flex items-center justify-between">
            <div className="flex items-center gap-2">
              <SlidersHorizontal size={15} className="text-glow" />
              <span className="font-mono text-xs font-semibold text-ink-100">
                {selected.id}
              </span>
              <span className="text-[11px] text-ink-500">
                · {selected["source-layer"] || selected.type}
              </span>
            </div>
            <button
              onClick={onClearSelection}
              className="grid h-6 w-6 place-items-center rounded text-ink-300 hover:bg-white/10 hover:text-ink-100"
              aria-label="Deselect layer"
            >
              <X size={14} />
            </button>
          </div>

          {(() => {
            const props = layerPropsFor(selected);
            if (!props.length)
              return <p className="text-[11px] text-ink-300">No editable paint properties.</p>;
            return props.map((p) => (
              <PropRow
                key={p.prop}
                prop={p.prop}
                kind={p.kind}
                value={selected.paint && selected.paint[p.prop]}
                onChange={(v) => onApplyProp(selected.id, p.prop, v)}
              />
            ));
          })()}
        </div>
      )}
    </div>
  );
}
