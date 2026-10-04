import { Sparkles } from "lucide-react";

const QUICK_PROMPTS = [
  { label: "Calm ocean", prompt: "Apply the ocean palette to make a calm coastal map." },
  { label: "Warm desert", prompt: "Apply the desert palette for a warm sandy look." },
  { label: "Night mode", prompt: "Apply the midnight palette and make roads and labels high contrast." },
  { label: "Vivid neon", prompt: "Apply the neon palette for a bold look." },
  { label: "Soft pastel", prompt: "Apply the pastel palette." },
  { label: "Bold highways", prompt: "Make the motorway and major highways bright and thick, and dim the minor roads." },
  { label: "Hide labels", prompt: "Hide all place-name and road-name labels." },
  { label: "Minimalist", prompt: "Apply the arctic palette and hide railways and minor details for a clean map." },
];

export default function QuickPrompts({ onQuick }) {
  return (
    <div className="pointer-events-none absolute inset-x-0 bottom-0 z-[5] px-3 pb-3">
      <div className="pointer-events-auto flex items-center gap-2 overflow-x-auto rounded-xl border border-line bg-ink-900/70 p-2 backdrop-blur-md">
        <span className="flex shrink-0 items-center gap-1.5 pl-1 text-xs text-ink-300">
          <Sparkles size={15} className="text-glow" />
          <span className="hidden sm:inline">Try</span>
        </span>
        {QUICK_PROMPTS.map((q) => (
          <button
            key={q.label}
            onClick={() => onQuick(q.prompt)}
            className="shrink-0 whitespace-nowrap rounded-full border border-line bg-ink-750 px-3 py-1.5 text-xs text-ink-200 transition hover:border-brand-500/60 hover:bg-ink-700 hover:text-ink-100"
          >
            {q.label}
          </button>
        ))}
      </div>
    </div>
  );
}
