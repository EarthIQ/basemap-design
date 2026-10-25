import { useMemo, useRef } from "react";
import type { ChangeEvent } from "react";
import { Copy, Download, Code2, Upload } from "lucide-react";
import Button from "@/components/ui/Button";
import { useToast } from "@/state/ToastContext";
import type { MapStyle } from "@/lib/types";

function buildEmbed(styleJson: string): string {
  return (
    `<link href="https://cdn.jsdelivr.net/npm/maplibre-gl@5.3.0/dist/maplibre-gl.css" rel="stylesheet">` +
    `<script src="https://cdn.jsdelivr.net/npm/maplibre-gl@5.3.0/dist/maplibre-gl.js"></script>` +
    `<div id="map" style="width:100%;height:100vh"></div>` +
    `<script>\nnew maplibregl.Map({ container:'map', style: ${styleJson}, attributionControl:true });\n</script>`
  );
}

type ExportTabProps = {
  style: MapStyle | null;
  onImport?: (style: MapStyle, sourceName: string) => void;
};

export default function ExportTab({ style, onImport }: ExportTabProps) {
  const { push: toast } = useToast();
  const fileRef = useRef<HTMLInputElement>(null);
  const json = useMemo(() => (style ? JSON.stringify(style, null, 2) : ""), [style]);

  async function copy(text: string, label: string) {
    try {
      await navigator.clipboard.writeText(text);
      toast(`${label} copied`, "ok");
    } catch (e) {
      toast("Copy failed: " + (e instanceof Error ? e.message : String(e)), "err");
    }
  }

  function download() {
    const name = (style && style.name) || "basemap";
    const blob = new Blob([json], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `${name.replace(/[^a-z0-9_-]/gi, "_")}.json`;
    a.click();
    URL.revokeObjectURL(url);
    toast("Downloaded", "ok");
  }

  function pickFile() {
    fileRef.current?.click();
  }

  async function onFile(e: ChangeEvent<HTMLInputElement>) {
    const input = e.target;
    const file = input.files?.[0];
    input.value = "";
    if (!file) return;
    let parsed: unknown;
    try {
      parsed = JSON.parse(await file.text());
    } catch {
      toast("That file is not valid JSON", "err");
      return;
    }
    if (
      !parsed ||
      typeof parsed !== "object" ||
      !(parsed as Record<string, unknown>).version ||
      !Array.isArray((parsed as Record<string, unknown>).layers)
    ) {
      toast("Not a MapLibre style JSON (needs version + layers)", "err");
      return;
    }
    onImport?.(parsed as MapStyle, file.name);
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="space-y-2 p-4">
        <h3 className="text-sm font-semibold text-ink-100">Import &amp; export the design</h3>
        <div className="flex flex-wrap gap-2">
          <Button size="sm" onClick={() => copy(json, "Style JSON")} disabled={!json}>
            <Copy size={14} />
            Copy JSON
          </Button>
          <Button size="sm" onClick={download} disabled={!json}>
            <Download size={14} />
            Download .json
          </Button>
          <Button
            size="sm"
            variant="ghost"
            onClick={() => copy(buildEmbed(json), "Embed snippet")}
            disabled={!json}
          >
            <Code2 size={14} />
            Copy MapLibre embed
          </Button>
          <Button size="sm" variant="ghost" onClick={pickFile} disabled={!onImport}>
            <Upload size={14} />
            Import .json
          </Button>
          <input
            ref={fileRef}
            type="file"
            accept="application/json,.json"
            className="hidden"
            onChange={onFile}
          />
        </div>
      </div>

      <textarea
        readOnly
        value={json}
        spellCheck={false}
        placeholder="Your style JSON…"
        className="min-h-[200px] flex-1 resize-none border-t border-line bg-ink-950 p-3 font-mono text-[11px] leading-relaxed text-ink-200 outline-none"
      />
    </div>
  );
}
