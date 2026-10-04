import {
  Bot,
  BrainCircuit,
  Wrench,
  CheckCircle2,
  XCircle,
  AlertTriangle,
  Loader2,
} from "lucide-react";
import { cn, shortArgs, summarizeResult } from "../../lib/utils";

function ThinkingBlock({ note, active }) {
  return (
    <div className="flex items-center gap-2 text-xs text-ink-300">
      {active ? (
        <Loader2 size={14} className="animate-spin text-glow" />
      ) : (
        <BrainCircuit size={14} className="text-ink-500" />
      )}
      <span className="italic">{note || "thinking…"}</span>
    </div>
  );
}

function TextBlock({ content, streaming }) {
  if (!content) return null;
  return (
    <div
      className={cn(
        "whitespace-pre-wrap break-words text-sm leading-relaxed text-ink-100",
        streaming && "stream-caret"
      )}
    >
      {content}
    </div>
  );
}

function ToolBlock({ name, args, status, result }) {
  const Icon = status === "running" ? Loader2 : status === "done" ? CheckCircle2 : XCircle;
  const tone =
    status === "done"
      ? "border-emerald-500/40 text-emerald-300"
      : status === "fail"
      ? "border-rose-500/50 text-rose-300"
      : "border-line text-ink-300";

  return (
    <div className={cn("rounded-lg border bg-ink-950/60 px-3 py-2", tone)}>
      <div className="flex items-center gap-2">
        <Icon size={15} className={cn(status === "running" && "animate-spin")} />
        <span className="font-mono text-xs font-medium text-ink-100">{name}</span>
        {args && Object.keys(args).length > 0 && (
          <span className="truncate font-mono text-[11px] text-ink-300">
            {shortArgs(args)}
          </span>
        )}
      </div>
      {status !== "running" && (
        <div className="mt-1 pl-[22px] font-mono text-[11px] text-ink-300">
          {summarizeResult(result)}
        </div>
      )}
    </div>
  );
}

function ErrorBlock({ message }) {
  return (
    <div className="flex items-start gap-2 rounded-lg border border-rose-500/50 bg-rose-500/10 px-3 py-2 text-xs text-rose-300">
      <AlertTriangle size={15} className="mt-0.5 shrink-0" />
      <span className="whitespace-pre-wrap break-words">{message}</span>
    </div>
  );
}

/** Render a single assistant turn as an ordered "what happened" timeline. */
export default function Turn({ turn }) {
  const running = turn.status === "running";
  const lastTextIdx = [...turn.parts]
    .map((p, i) => ({ p, i }))
    .filter(({ p }) => p.kind === "text")
    .pop()?.i;

  return (
    <div className="animate-fade-in flex flex-col gap-1.5">
      <div className="flex items-center gap-2">
        <div className="grid h-5 w-5 place-items-center rounded-md bg-gradient-to-br from-brand-500 to-glow">
          <Bot size={13} className="text-white" />
        </div>
        <span className="text-[11px] font-semibold uppercase tracking-wider text-ink-300">
          EarthIQ
        </span>
        {running && (
          <span className="flex items-center gap-1 text-[11px] text-ink-300">
            <Loader2 size={11} className="animate-spin" />
            working
          </span>
        )}
      </div>

      <div className="ml-1 flex flex-col gap-2 border-l border-line pl-3">
        {turn.parts.length === 0 && running && <ThinkingBlock note="thinking…" active />}
        {turn.parts.map((part, i) => {
          switch (part.kind) {
            case "thinking":
              return (
                <ThinkingBlock
                  key={part.id}
                  note={part.note}
                  active={running && i === 0 && turn.parts[1]?.kind !== "text"}
                />
              );
            case "text":
              return (
                <TextBlock
                  key={part.id}
                  content={part.content}
                  streaming={running && i === lastTextIdx}
                />
              );
            case "tool":
              return (
                <ToolBlock
                  key={part.id}
                  name={part.name}
                  args={part.args}
                  status={part.status}
                  result={part.result}
                />
              );
            case "error":
              return <ErrorBlock key={part.id} message={part.message} />;
            default:
              return null;
          }
        })}
      </div>
    </div>
  );
}
