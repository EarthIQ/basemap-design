import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Compass } from "lucide-react";
import { api } from "./lib/api";
import { applyActions } from "./lib/maplibre";
import { useToast } from "./state/ToastContext.jsx";
import Header from "./components/Header.jsx";
import SettingsPanel from "./components/SettingsPanel.jsx";
import MapView from "./components/MapView.jsx";
import Sidebar from "./components/Sidebar.jsx";
import AITab from "./components/chat/AITab.jsx";
import PalettesTab from "./components/tabs/PalettesTab.jsx";
import InspectorTab from "./components/tabs/InspectorTab.jsx";
import ExportTab from "./components/tabs/ExportTab.jsx";

export default function App() {
  const { push: toast } = useToast();

  const [ready, setReady] = useState(false);
  const [fatal, setFatal] = useState(null);

  const [settings, setSettings] = useState(null);
  const [provider, setProvider] = useState("ollama");
  const [model, setModel] = useState("");
  const [models, setModels] = useState([]);
  const [baseStyles, setBaseStyles] = useState([]);
  const [palettes, setPalettes] = useState([]);
  const [style, setStyle] = useState(null);
  const [overview, setOverview] = useState(null);
  const [selectedLayer, setSelectedLayer] = useState(null);
  const [activeTab, setActiveTab] = useState("ai");
  const [showSettings, setShowSettings] = useState(false);
  const [health, setHealth] = useState(null);

  const mapRef = useRef(null);
  const sendPromptRef = useRef(null);

  const currentBase = (style?.name || "").split(":")[1] || "";
  const styleName = style?.name || "";

  /* ---------------------------------------------------------- map sync --- */
  const apply = useCallback((actions) => {
    if (mapRef.current) applyActions(mapRef.current, actions);
  }, []);

  const refreshStyle = useCallback(async () => {
    try {
      const [s, o] = await Promise.all([
        api("/api/session/style"),
        api("/api/session/overview").catch(() => null),
      ]);
      setStyle(s);
      if (o) setOverview(o);
    } catch (e) {
      /* transient; keep last good state */
    }
  }, []);

  const applyAndSync = useCallback(
    async (actions) => {
      apply(actions);
      await refreshStyle();
    },
    [apply, refreshStyle]
  );

  /* ----------------------------------------------------- status + models --- */
  const refreshStatus = useCallback(async () => {
    try {
      setHealth(await api("/api/health"));
    } catch (e) {
      setHealth(null);
    }
  }, []);

  const refreshModels = useCallback(async (p) => {
    try {
      const r = await api(`/api/models?provider=${encodeURIComponent(p)}`);
      setModels(r.models || []);
    } catch (e) {
      setModels([]);
    }
  }, []);

  /* ---------------------------------------------------------- initial load --- */
  useEffect(() => {
    (async () => {
      try {
        const [s, cfg, pal, ov, h] = await Promise.all([
          api("/api/session/style"),
          api("/api/settings"),
          api("/api/palettes"),
          api("/api/session/overview").catch(() => null),
          api("/api/health").catch(() => null),
        ]);
        setStyle(s);
        setSettings(cfg);
        setPalettes(pal.palettes || []);
        setBaseStyles(cfg.baseStyles || []);
        const prov = cfg.provider || "ollama";
        setProvider(prov);
        setModel(
          prov === "ollama" ? cfg.ollama?.model || "" : cfg.openai?.model || ""
        );
        setOverview(ov);
        setHealth(h);
        refreshModels(prov);
      } catch (e) {
        setFatal(e.message || String(e));
      } finally {
        setReady(true);
      }
    })();
  }, [refreshModels]);

  /* ------------------------------------------------------------- handlers --- */
  function handleBaseChange(name) {
    if (!name) return;
    (async () => {
      try {
        const r = await api("/api/session/load", { method: "POST", body: { name } });
        if (r.actions?.[0]?.style) setStyle(r.actions[0].style);
        applyAndSync(r.actions);
        setSelectedLayer(null);
        toast(`Loaded base map: ${name}`, "ok");
      } catch (e) {
        toast(e.message, "err");
      }
    })();
  }

  function handleProviderChange(p) {
    const norm = p === "openai_compatible" ? "openai" : "ollama";
    setProvider(norm);
    refreshModels(norm);
    refreshStatus();
  }

  function handleApplyPalette(name) {
    (async () => {
      try {
        const r = await api("/api/apply", {
          method: "POST",
          body: { name: "apply_palette", args: { name } },
        });
        applyAndSync(r.actions);
        toast(`Applied ${name}`, "ok");
      } catch (e) {
        toast(e.message, "err");
      }
    })();
  }

  function handleToggleVis(layerId, visible) {
    (async () => {
      try {
        const r = await api("/api/apply", {
          method: "POST",
          body: { name: "set_visibility", args: { layer_id: layerId, visible } },
        });
        applyAndSync(r.actions);
      } catch (e) {
        toast(e.message, "err");
      }
    })();
  }

  function handleApplyProp(layerId, prop, value) {
    (async () => {
      try {
        const r = await api("/api/apply", {
          method: "POST",
          body: { name: "update_layer", args: { layer_id: layerId, paint: { [prop]: value } } },
        });
        if (r.result && r.result.ok === false) {
          toast(r.result.error || "failed", "err");
          return;
        }
        applyAndSync(r.actions);
      } catch (e) {
        toast(e.message, "err");
      }
    })();
  }

  function handleSaveSettings(body) {
    (async () => {
      try {
        const s = await api("/api/settings", { method: "POST", body });
        setSettings(s);
        refreshStyle();
        refreshStatus();
        setShowSettings(false);
        toast("Settings saved", "ok");
      } catch (e) {
        toast(e.message, "err");
      }
    })();
  }

  function handleQuick(prompt) {
    setActiveTab("ai");
    setTimeout(() => sendPromptRef.current?.(prompt), 0);
  }

  function handleImport(styleJson, sourceName) {
    (async () => {
      try {
        const name = sourceName ? sourceName.replace(/\.json$/i, "") : undefined;
        const r = await api("/api/session/import", {
          method: "POST",
          body: { style: styleJson, name },
        });
        if (r.actions?.[0]?.style) setStyle(r.actions[0].style);
        applyAndSync(r.actions);
        setSelectedLayer(null);
        toast("Imported style from JSON", "ok");
      } catch (e) {
        toast(e.message, "err");
      }
    })();
  }

  function registerSend(fn) {
    sendPromptRef.current = fn;
  }

  /* -------------------------------------------------------------- status --- */
  const status = useMemo(() => {
    if (provider === "ollama") {
      if (health?.ollama?.ok)
        return {
          s: "ok",
          title: `Ollama ${health.ollama.version || ""} \u00b7 ${health.ollama.models?.length || 0} model(s)`.trim(),
        };
      return {
        s: "off",
        title: `Ollama not reachable at ${health?.ollama?.baseUrl || settings?.ollama?.baseUrl || ""}`.trim(),
      };
    }
    if (settings?.openai?.hasKey) return { s: "ok", title: "OpenAI-compatible (key set)" };
    return { s: "warn", title: "OpenAI-compatible: no API key set (open Settings)" };
  }, [provider, health, settings]);

  /* -------------------------------------------------------------- render --- */
  if (fatal) return <ErrorScreen message={fatal} />;
  if (!ready) return <LoadingScreen />;

  return (
    <div className="flex h-full flex-col">
      <Header
        baseStyles={baseStyles}
        currentBase={currentBase}
        onBaseChange={handleBaseChange}
        onToggleSettings={() => setShowSettings((v) => !v)}
        status={status.s}
        statusTitle={status.title}
      />

      {showSettings && settings && (
        <SettingsPanel
          settings={settings}
          onSave={handleSaveSettings}
          onClose={() => setShowSettings(false)}
          provider={provider}
          onProviderChange={handleProviderChange}
          model={model}
          onModelChange={setModel}
          models={models}
        />
      )}

      <div className="flex min-h-0 flex-1 flex-col lg:flex-row">
        <Sidebar activeTab={activeTab} onTabChange={setActiveTab}>
          {activeTab === "ai" && (
            <AITab
              provider={provider}
              model={model}
              applyAndSync={applyAndSync}
              refreshStyle={refreshStyle}
              onRegisterSend={registerSend}
            />
          )}
          {activeTab === "palettes" && (
            <PalettesTab
              palettes={palettes}
              onApply={handleApplyPalette}
              baseStyles={baseStyles}
              currentBase={currentBase}
              onLoadBase={handleBaseChange}
            />
          )}
          {activeTab === "inspector" && (
            <InspectorTab
              overview={overview}
              selectedLayer={selectedLayer}
              onSelectLayer={setSelectedLayer}
              onClearSelection={() => setSelectedLayer(null)}
              onToggleVis={handleToggleVis}
              onApplyProp={handleApplyProp}
            />
          )}
          {activeTab === "export" && <ExportTab style={style} onImport={handleImport} />}
        </Sidebar>

        <MapView
          initialStyle={style}
          onMap={(m) => (mapRef.current = m)}
          styleName={styleName}
          onQuick={handleQuick}
        />
      </div>
    </div>
  );
}

/* ------------------------------------------------------------ boot screens --- */
function LoadingScreen() {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-4 bg-ink-950 text-ink-200">
      <div className="grid h-14 w-14 place-items-center rounded-2xl bg-gradient-to-br from-brand-500 to-glow">
        <Compass size={28} className="animate-pulse text-white" />
      </div>
      <div className="flex flex-col items-center gap-1">
        <span className="text-sm font-medium text-ink-100">EarthIQ</span>
        <span className="text-xs text-ink-400">Preparing your base map\u2026</span>
      </div>
    </div>
  );
}

function ErrorScreen({ message }) {
  return (
    <div className="flex h-full items-center justify-center bg-ink-950 px-6">
      <div className="max-w-md rounded-2xl border border-rose-500/40 bg-rose-500/10 p-6 text-center">
        <div className="mb-2 text-sm font-semibold text-rose-200">Could not start EarthIQ</div>
        <p className="text-sm text-rose-200/80">{message}</p>
        <p className="mt-3 text-xs text-ink-400">
          Make sure the backend is running (`./run.sh`) and try reloading.
        </p>
      </div>
    </div>
  );
}
