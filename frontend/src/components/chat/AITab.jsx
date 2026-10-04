import { useCallback, useEffect, useRef, useState } from "react";
import { Send, Square, Eraser } from "lucide-react";
import Button from "../ui/Button.jsx";
import Turn from "./Turn.jsx";
import { streamChat } from "../../lib/api";
import { uid } from "../../lib/utils";
import { useToast } from "../../state/ToastContext.jsx";

const WELCOME = {
  id: "welcome",
  role: "assistant",
  status: "done",
  parts: [
    {
      id: "welcome-text",
      kind: "text",
      content:
        "Hi! I design base maps for you on top of OpenFreeMap vector data.",
    },
  ],
};

export default function AITab({
  provider,
  model,
  applyAndSync,
  refreshStyle,
  onRegisterSend,
}) {
  const [messages, setMessages] = useState([WELCOME]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const { push: toast } = useToast();
  const scrollRef = useRef(null);
  const controllerRef = useRef(null);

  // Keep the chat pinned to the latest block as the stream updates.
  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages]);

  const updateTurn = useCallback((id, updater) => {
    setMessages((msgs) => msgs.map((m) => (m.id === id ? updater(m) : m)));
  }, []);

  const sendPrompt = useCallback(
    async (text) => {
      const message = (text || "").trim();
      if (!message) return;

      const abort = new AbortController();
      controllerRef.current = abort;
      setBusy(true);
      setInput("");

      const userMsg = { id: uid("msg"), role: "user", text: message };
      const turnId = uid("turn");
      setMessages((m) => [
        ...m,
        userMsg,
        { id: turnId, role: "assistant", status: "running", parts: [] },
      ]);

      const addPart = (part) =>
        updateTurn(turnId, (t) => ({ ...t, parts: [...t.parts, part] }));
      const appendText = (delta) =>
        updateTurn(turnId, (t) => {
          const parts = [...t.parts];
          const last = parts[parts.length - 1];
          if (last && last.kind === "text") {
            parts[parts.length - 1] = { ...last, content: last.content + delta };
          } else {
            parts.push({ id: uid("b"), kind: "text", content: delta });
          }
          return { ...t, parts };
        });
      const finishLastTool = (ev) =>
        updateTurn(turnId, (t) => {
          const parts = [...t.parts];
          for (let i = parts.length - 1; i >= 0; i--) {
            if (parts[i].kind === "tool" && parts[i].status === "running") {
              parts[i] = {
                ...parts[i],
                status: ev.result && ev.result.ok !== false ? "done" : "fail",
                result: ev.result,
              };
              break;
            }
          }
          return { ...t, parts };
        });

      try {
        for await (const ev of streamChat({ message, provider, model })) {
          if (abort.signal.aborted) break;
          switch (ev.type) {
            case "thinking":
              addPart({ id: uid("b"), kind: "thinking", note: ev.note });
              break;
            case "assistant_delta":
              appendText(ev.content || "");
              break;
            case "assistant":
              updateTurn(turnId, (t) => {
                if (!ev.content) return t;
                if (t.parts.some((p) => p.kind === "text")) return t;
                return {
                  ...t,
                  parts: [...t.parts, { id: uid("b"), kind: "text", content: ev.content }],
                };
              });
              break;
            case "tool_call":
              addPart({
                id: uid("b"),
                kind: "tool",
                name: ev.name,
                args: ev.arguments,
                status: "running",
                result: null,
              });
              break;
            case "tool_result":
              finishLastTool(ev);
              if (ev.actions) applyAndSync(ev.actions);
              break;
            case "error":
              updateTurn(turnId, (t) => ({
                ...t,
                status: "error",
                parts: [...t.parts, { id: uid("b"), kind: "error", message: ev.message }],
              }));
              break;
            case "done":
              updateTurn(turnId, (t) => ({ ...t, status: "done" }));
              refreshStyle();
              break;
            default:
              break;
          }
        }

        updateTurn(turnId, (t) =>
          t.status === "running" ? { ...t, status: "done" } : t
        );
      } catch (e) {
        if (abort.signal.aborted) {
          updateTurn(turnId, (t) => ({ ...t, status: "done" }));
        } else {
          updateTurn(turnId, (t) => ({
            ...t,
            status: "error",
            parts: [...t.parts, { id: uid("b"), kind: "error", message: e.message }],
          }));
        }
      } finally {
        setBusy(false);
      }
    },
    [provider, model, updateTurn, applyAndSync, refreshStyle]
  );

  // Expose sendPrompt so quick prompts (on the map) can trigger a chat.
  useEffect(() => {
    onRegisterSend?.(sendPrompt);
  }, [sendPrompt, onRegisterSend]);

  function stop() {
    controllerRef.current?.abort();
  }

  function clearChat() {
    controllerRef.current?.abort();
    setMessages([WELCOME]);
    setInput("");
    setBusy(false);
    toast("Chat cleared", "ok");
  }

  function onKeyDown(e) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendPrompt(input);
    }
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="flex items-center justify-between border-b border-line px-4 py-2">
        <span className="text-[11px] font-medium uppercase tracking-wider text-ink-400">
          AI assistant
        </span>
        <button
          onClick={clearChat}
          disabled={busy || messages.length <= 1}
          title="Clear chat"
          className="flex items-center gap-1.5 rounded-md px-2 py-1 text-[11px] font-medium text-ink-400 transition hover:bg-white/5 hover:text-ink-100 disabled:cursor-not-allowed disabled:opacity-40"
        >
          <Eraser size={13} />
          Clear chat
        </button>
      </div>
      <div ref={scrollRef} className="flex-1 space-y-5 overflow-y-auto p-4">
        {messages.map((m) =>
          m.role === "user" ? (
            <div key={m.id} className="flex flex-col items-end gap-1">
              <span className="text-[11px] font-semibold uppercase tracking-wider text-brand-400">
                You
              </span>
              <div className="max-w-[85%] whitespace-pre-wrap rounded-xl rounded-br-sm border border-brand-500/30 bg-brand-500/10 px-3.5 py-2 text-sm text-ink-100">
                {m.text}
              </div>
            </div>
          ) : (
            <Turn key={m.id} turn={m} />
          )
        )}
      </div>

      <div className="border-t border-line p-3">
        <div className="flex items-end gap-2 rounded-xl border border-line bg-ink-850 p-2 focus-within:border-brand-500">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={onKeyDown}
            rows={2}
            placeholder="Describe your map… e.g. calm ocean, warm desert, night mode"
            className="max-h-40 flex-1 resize-none bg-transparent px-2 py-1.5 text-sm text-ink-100 outline-none placeholder:text-ink-500"
          />
          {busy ? (
            <Button
              variant="default"
              size="sm"
              className="p-2!"
              onClick={stop}
              title="Stop"
            >
              <Square size={15} />
            </Button>
          ) : (
            <Button
              variant="primary"
              size="sm"
              className="p-2!"
              onClick={() => sendPrompt(input)}
              disabled={!input.trim()}
              title="Send"
            >
              <Send size={15} />
            </Button>
          )}
        </div>
        <p className="mt-1.5 px-1 text-[11px] text-ink-500">Enter to send · Shift+Enter for a new line</p>
      </div>
    </div>
  );
}
