import { Palette, Layers, Check } from "lucide-react";
import { titleCase } from "../../lib/utils";

function PaletteCard({ palette, onApply }) {
  const swatches = (palette.swatches || []).slice(0, 8);
  return (
    <div className="group flex flex-col gap-2 rounded-xl border border-line bg-ink-850 p-3 transition hover:border-brand-500/50">
      <div className="flex h-5 overflow-hidden rounded-md">
        {swatches.map((c, i) => (
          <span key={i} className="flex-1" style={{ background: c || "#888" }} />
        ))}
      </div>
      <div className="flex flex-1 flex-col">
        <span className="text-sm font-semibold text-ink-100">{palette.label}</span>
        <span className="mt-0.5 text-[11px] leading-snug text-ink-300">
          {palette.description}
        </span>
      </div>
      <button
        onClick={() => onApply(palette.name)}
        className="mt-1 inline-flex items-center justify-center gap-1.5 rounded-lg border border-line bg-ink-750 px-3 py-1.5 text-xs font-medium text-ink-200 transition hover:border-brand-500/60 hover:bg-brand-500/15 hover:text-ink-100"
      >
        <Check size={13} />
        Apply
      </button>
    </div>
  );
}

export default function PalettesTab({
  palettes = [],
  onApply,
  baseStyles = [],
  currentBase = "",
  onLoadBase,
}) {
  return (
    <div className="flex-1 space-y-5 overflow-y-auto p-4">
      <div>
        <div className="mb-3 flex items-center gap-2">
          <Palette size={16} className="text-glow" />
          <h3 className="text-sm font-semibold text-ink-100">Curated palettes</h3>
          <span className="text-[11px] text-ink-500">applied to the current base map</span>
        </div>
        <div className="grid grid-cols-2 gap-3">
          {palettes.map((p) => (
            <PaletteCard key={p.name} palette={p} onApply={onApply} />
          ))}
          {palettes.length === 0 && (
            <p className="col-span-2 text-sm text-ink-300">No palettes available.</p>
          )}
        </div>
      </div>

      <div>
        <div className="mb-3 flex items-center gap-2">
          <Layers size={16} className="text-glow" />
          <h3 className="text-sm font-semibold text-ink-100">Base styles</h3>
          <span className="text-[11px] text-ink-500">full OpenFreeMap maps</span>
        </div>
        <div className="flex flex-wrap gap-2">
          {baseStyles.map((n) => (
            <button
              key={n}
              onClick={() => onLoadBase(n)}
              className={
                "rounded-lg border px-3.5 py-2 text-sm capitalize transition " +
                (currentBase === n
                  ? "border-brand-500 bg-brand-500/15 text-ink-100"
                  : "border-line bg-ink-750 text-ink-200 hover:border-brand-500/60")
              }
            >
              {titleCase(n)}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}
