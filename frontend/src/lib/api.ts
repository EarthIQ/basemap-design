import type { SSEEvent } from "@/lib/types";

type ApiOptions = Omit<RequestInit, "body"> & { body?: unknown };

/** Thin JSON fetch helper with consistent error messages. */
export async function api<T = unknown>(path: string, opts: ApiOptions = {}): Promise<T> {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...opts,
    body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined,
  });
  if (!res.ok) {
    let detail = "";
    try {
      detail = ((await res.json()) as { detail?: string }).detail || "";
    } catch {
      /* not JSON */
    }
    throw new Error([res.status, res.statusText, detail].filter(Boolean).join(" ").trim());
  }
  return (await res.json()) as T;
}

/**
 * POST a chat turn and yield parsed SSE events as an async generator, so the
 * UI can render assistant text token-by-token as it arrives.
 */
export async function* streamChat(args: {
  message: string;
  provider?: string;
  model?: string;
}): AsyncGenerator<SSEEvent, void, unknown> {
  const res = await fetch("/api/chat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(args),
  });

  if (!res.ok || !res.body) {
    let detail = "";
    try {
      detail = ((await res.json()) as { detail?: string }).detail || res.statusText;
    } catch {
      detail = res.statusText || "request failed";
    }
    throw new Error(detail || `Chat request failed (${res.status})`);
  }

  const reader = res.body.getReader();
  const dec = new TextDecoder();
  let buf = "";

  while (true) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += dec.decode(value, { stream: true });

    let idx: number;
    while ((idx = buf.indexOf("\n\n")) >= 0) {
      const frame = buf.slice(0, idx);
      buf = buf.slice(idx + 2);
      const line = frame.split("\n").find((l) => l.startsWith("data:"));
      if (!line) continue;
      const payload = line.slice(5).trim();
      if (payload === "[DONE]") return;
      try {
        yield JSON.parse(payload) as SSEEvent;
      } catch {
        /* ignore malformed frames */
      }
    }
  }
}
