import { useState } from "react";
import { X, Save } from "lucide-react";
import Button from "./ui/Button.jsx";
import { cn } from "../lib/utils";

const fieldCls =
  "rounded-lg border border-line bg-ink-850 px-3 py-2 text-sm text-ink-100 outline-none transition focus:border-brand-500";

function Labeled({ label, ...rest }) {
  return (
    <label className="flex flex-col gap-1.5 text-xs text-ink-300">
      <span>{label}</span>
      <input className={fieldCls} {...rest} />
    </label>
  );
}

function SelectField({ label, children, className }) {
  return (
    <label className={cn("flex flex-col gap-1.5 text-xs text-ink-300", className)}>
      <span>{label}</span>
      {children}
    </label>
  );
}

export default function SettingsPanel({
  settings,
  onSave,
  onClose,
  provider = "ollama",
  onProviderChange,
  model = "",
  onModelChange,
  models = [],
}) {
  const [tileBaseUrl, setTileBaseUrl] = useState(settings.tileBaseUrl || "");
  const [ollamaBaseUrl, setOllamaBaseUrl] = useState(settings.ollama?.baseUrl || "");
  const [openaiBaseUrl, setOpenaiBaseUrl] = useState(settings.openai?.baseUrl || "");
  const [openaiApiKey, setOpenaiApiKey] = useState("");
  const [busy, setBusy] = useState(false);

  const providerDisplay = provider === "ollama" ? "ollama" : "openai_compatible";

  async function handleSave() {
    setBusy(true);
    try {
      await onSave({
        tileBaseUrl,
        ollamaBaseUrl,
        openaiBaseUrl,
        openaiApiKey: openaiApiKey || undefined,
      });
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="animate-fade-in border-b border-line bg-ink-850 px-4 py-3">
      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-sm font-semibold text-ink-100">Settings</h2>
        <button
          onClick={onClose}
          className="grid h-7 w-7 place-items-center rounded-md text-ink-300 transition hover:bg-white/5 hover:text-ink-100"
          aria-label="Close settings"
        >
          <X size={16} />
        </button>
      </div>

      {/* Engine & model, applied immediately (no save needed). */}
      <div className="mb-1 text-[11px] font-medium uppercase tracking-wider text-ink-400">
        AI engine
      </div>
      <div className="mb-4 grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
        <SelectField label="Engine">
          <select
            className={fieldCls}
            value={providerDisplay}
            onChange={(e) => onProviderChange?.(e.target.value)}
          >
            <option value="ollama">Ollama (local)</option>
            <option value="openai_compatible">OpenAI-compatible</option>
          </select>
        </SelectField>
        <SelectField label="Model" className="md:col-span-2">
          <input
            list="earthiq-models"
            value={model}
            onChange={(e) => onModelChange?.(e.target.value)}
            placeholder={provider === "ollama" ? "e.g. qwen2.5:14b" : "e.g. gpt-4.1-mini"}
            className={fieldCls}
          />
          <datalist id="earthiq-models">
            {models.map((m) => (
              <option key={m} value={m} />
            ))}
          </datalist>
        </SelectField>
      </div>

      {/* Connection settings, require Save & apply. */}
      <div className="mb-1 text-[11px] font-medium uppercase tracking-wider text-ink-400">
        Connections
      </div>
      <div className="grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-4">
        <Labeled
          label="Tile base URL (self-host OpenFreeMap)"
          value={tileBaseUrl}
          onChange={(e) => setTileBaseUrl(e.target.value)}
          placeholder="https://tiles.openfreemap.org"
        />
        <Labeled
          label="Ollama base URL"
          value={ollamaBaseUrl}
          onChange={(e) => setOllamaBaseUrl(e.target.value)}
          placeholder="http://localhost:11444"
        />
        <Labeled
          label="OpenAI-compatible base URL"
          value={openaiBaseUrl}
          onChange={(e) => setOpenaiBaseUrl(e.target.value)}
          placeholder="https://openrouter.ai/api/v1"
        />
        <Labeled
          label="OpenAI API key"
          type="password"
          value={openaiApiKey}
          onChange={(e) => setOpenaiApiKey(e.target.value)}
          placeholder="sk-…"
        />
      </div>

      <div className="mt-3 flex items-center gap-3">
        <Button variant="primary" size="sm" onClick={handleSave} loading={busy}>
          <Save size={15} />
          Save &amp; apply
        </Button>
        <span className={cn("text-xs text-ink-300")}>
          Keys are stored only in this server&apos;s memory.
        </span>
      </div>
    </div>
  );
}
