import { createContext, useCallback, useContext, useMemo, useRef, useState } from "react";
import { CheckCircle2, XCircle, Info, X } from "lucide-react";
import { cn, uid } from "../lib/utils";

const ToastContext = createContext({ push: () => {} });

const ICONS = {
  ok: CheckCircle2,
  err: XCircle,
  info: Info,
};

const ACCENTS = {
  ok: "border-emerald-500/50 text-emerald-300",
  err: "border-rose-500/50 text-rose-300",
  info: "border-sky-500/50 text-sky-300",
};

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([]);
  const timers = useRef({});

  const dismiss = useCallback((id) => {
    setToasts((t) => t.filter((x) => x.id !== id));
    clearTimeout(timers.current[id]);
    delete timers.current[id];
  }, []);

  const push = useCallback(
    (message, kind = "info", ttl = 3000) => {
      const id = uid("toast");
      setToasts((t) => [...t, { id, message, kind }]);
      timers.current[id] = setTimeout(() => dismiss(id), ttl);
      return id;
    },
    [dismiss]
  );

  const value = useMemo(() => ({ push, dismiss }), [push, dismiss]);

  return (
    <ToastContext.Provider value={value}>
      {children}
      <div className="pointer-events-none fixed bottom-5 left-1/2 z-50 flex w-full max-w-md -translate-x-1/2 flex-col items-center gap-2 px-4">
        {toasts.map((t) => {
          const Icon = ICONS[t.kind] || Info;
          return (
            <div
              key={t.id}
              className={cn(
                "pointer-events-auto flex w-full items-start gap-3 rounded-xl border bg-zinc-900/95 px-4 py-3 shadow-lg shadow-black/40 backdrop-blur",
                ACCENTS[t.kind] || ACCENTS.info
              )}
            >
              <Icon size={18} className="mt-0.5 shrink-0" />
              <span className="flex-1 text-sm text-zinc-100">{t.message}</span>
              <button
                onClick={() => dismiss(t.id)}
                className="shrink-0 rounded-md p-1 text-zinc-500 transition hover:bg-white/10 hover:text-zinc-200"
                aria-label="Dismiss"
              >
                <X size={14} />
              </button>
            </div>
          );
        })}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  return useContext(ToastContext);
}
