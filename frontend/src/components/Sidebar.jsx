import { MessageSquareText, Palette, SlidersHorizontal, Download } from "lucide-react";
import { cn } from "../lib/utils";

const TABS = [
  { id: "ai", label: "AI", icon: MessageSquareText },
  { id: "palettes", label: "Palettes", icon: Palette },
  { id: "inspector", label: "Inspector", icon: SlidersHorizontal },
  { id: "export", label: "Export", icon: Download },
];

export default function Sidebar({ activeTab, onTabChange, children }) {
  return (
    <aside className="flex w-full flex-col border-t border-line bg-ink-900 lg:w-[380px] lg:min-w-[340px] lg:border-r lg:border-t-0">
      <nav className="flex border-b border-line">
        {TABS.map((t) => {
          const Icon = t.icon;
          const active = activeTab === t.id;
          return (
            <button
              key={t.id}
              onClick={() => onTabChange(t.id)}
              className={cn(
                "flex flex-1 flex-col items-center gap-1 border-b-2 py-2.5 text-[11px] font-medium transition",
                active
                  ? "border-brand-500 text-ink-100"
                  : "border-transparent text-ink-400 hover:text-ink-200"
              )}
            >
              <Icon size={17} className={active ? "text-brand-400" : ""} />
              {t.label}
            </button>
          );
        })}
      </nav>
      <div className="flex min-h-0 flex-1 flex-col">{children}</div>
    </aside>
  );
}
