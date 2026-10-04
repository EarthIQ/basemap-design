import { Compass, Layers, Settings2 } from "lucide-react";
import { cn, titleCase } from "../lib/utils";

function Field({ label, children, grow }) {
  return (
    <label className={cn("flex items-center gap-2 text-xs text-ink-300", grow && "flex-1 min-w-[160px]")}>
      <span className="hidden sm:inline whitespace-nowrap">{label}</span>
      {children}
    </label>
  );
}

const selectCls =
  "rounded-lg border border-line bg-ink-750 px-2.5 py-1.5 text-sm text-ink-100 outline-none transition focus:border-brand-500";

export default function Header({
  baseStyles = [],
  currentBase = "",
  onBaseChange,
  onToggleSettings,
  status = "off",
  statusTitle = "",
}) {

  return (
    <header className="flex flex-wrap items-center justify-between gap-3 border-b border-line bg-ink-900 px-4 py-2.5">
      {/* Brand */}
      <div className="flex items-center gap-3">
        <div className="grid h-9 w-9 place-items-center rounded-xl bg-gradient-to-br from-brand-500 to-glow shadow-md shadow-brand-500/20">
          <Compass size={20} className="text-white" strokeWidth={2.2} />
        </div>
        <div className="flex flex-col leading-tight">
          <span className="text-[15px] font-semibold tracking-tight text-ink-100">EarthIQ</span>
          <span className="text-[11px] text-ink-300">
            AI base map designer · OpenFreeMap
          </span>
        </div>
      </div>

      {/* Controls */}
      <div className="flex flex-wrap items-center gap-2.5">
        <Field label="Base">
          <span className="relative inline-flex items-center">
            <Layers size={14} className="pointer-events-none absolute left-2 text-ink-300" />
            <select
              className={cn(selectCls, "pl-7")}
              value={currentBase}
              onChange={(e) => onBaseChange(e.target.value)}
            >
              {baseStyles.map((n) => (
                <option key={n} value={n}>
                  {titleCase(n)}
                </option>
              ))}
            </select>
          </span>
        </Field>

        <button
          onClick={onToggleSettings}
          title="Settings"
          className="grid h-9 w-9 place-items-center rounded-lg border border-line bg-ink-750 text-ink-200 transition hover:border-brand-500/60 hover:text-ink-100"
        >
          <Settings2 size={18} />
        </button>

        <span
          title={statusTitle}
          className={cn(
            "h-2.5 w-2.5 rounded-full transition",
            status === "ok" && "bg-emerald-400 shadow-[0_0_8px] shadow-emerald-400/70",
            status === "warn" && "bg-amber-400 shadow-[0_0_8px] shadow-amber-400/70",
            status === "off" && "bg-rose-500"
          )}
        />
      </div>
    </header>
  );
}
