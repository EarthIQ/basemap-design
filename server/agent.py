"""The EarthIQ agent: a tool-calling loop that yields streamable events.

The session dict carries the mutable design state:

    {
      "style":   dict   # current MapLibre style (source of truth)
      "history": list    # unified conversation messages (persist across turns)
      "config":  dict    # provider / baseUrl / model / apiKey
      "name":    str     # base style this session started from (optional)
    }

``run_agent(session, user_message)`` is a generator that yields plain dicts.
``main.py`` serialises them as Server-Sent Events. Event types:

    start, thinking, assistant_delta, assistant, tool_call, tool_result, done, error
"""
from __future__ import annotations

import json
from typing import Any

from . import design, llm, settings

_MAX_HISTORY = 40  # keep context bounded (roughly the last N messages)


def build_system_prompt() -> str:
    base_styles = ", ".join(settings.BASE_STYLES)
    palettes = ", ".join(f"{p} ({design.PALETTES[p]['label']})" for p in design.PALETTES)
    return design.SYSTEM_PROMPT.format(base_styles=base_styles, palettes=palettes)


def trim_history(history: list[dict]) -> None:
    if len(history) > _MAX_HISTORY:
        del history[: len(history) - _MAX_HISTORY]


def _fallback_action(content: str):
    """Extract a tool call from an 'ACTION: <tool> [arg=value]' line in text.

    Gives small local models a reliable way to act even when their tool-call
    JSON is malformed or they simply describe the action instead.
    """
    m = settings.ACTION_LINE_RE.search(content or "")
    if not m or not m.group(1):
        return []
    name = m.group(1).lower()
    if name not in design.TOOL_FNS:
        return []
    args: dict[str, Any] = {}
    if m.group(2) and m.group(3):
        key = m.group(2).lower().replace("-", "_").strip()
        val = m.group(3).strip("`'\"")
        if name in ("apply_palette", "load_preset", "get_preset") and key != "name":
            key = "name"
        if name in ("remove_layer", "move_layer", "set_visibility") and key == "name":
            key = "layer_id"
        args[key] = val
    return [{"id": "fallback", "name": name, "arguments": args}]


def run_agent(session: dict[str, Any], user_message: str):
    """Generator yielding event dicts for one user turn."""
    # Build the effective LLM config from live settings (so provider/model
    # chosen in the UI actually take effect), then allow per-session overrides.
    provider = getattr(settings, "CURRENT_PROVIDER", "ollama")
    config: dict[str, Any] = {
        "provider": provider,
        "baseUrl": settings.OLLAMA_BASE_URL,
        "model": settings.DEFAULT_OLLAMA_MODEL,
        "apiKey": settings.OPENAI_API_KEY,
    }
    if provider != "ollama":
        config["baseUrl"] = settings.OPENAI_BASE_URL
        config["model"] = settings.OPENAI_MODEL
    config.update(session.get("config") or {})

    style = session["style"]
    history: list[dict] = session.setdefault("history", [])
    history.append({"role": "user", "content": user_message})
    trim_history(history)

    messages: list[dict] = [{"role": "system", "content": build_system_prompt()}] + list(history)

    def push(msg: dict) -> None:
        messages.append(msg)
        history.append(msg)

    yield {"type": "start", "model": config.get("model"), "provider": config.get("provider")}

    try:
        for step in range(settings.MAX_AGENT_STEPS):
            yield {"type": "thinking", "note": f"reasoning (step {step + 1})"}
            content = ""
            tool_calls: list[dict] = []
            for item in llm.stream_chat(config, messages, design.TOOLS):
                if item["type"] == "delta":
                    content += item["text"]
                    yield {"type": "assistant_delta", "content": item["text"]}
                else:
                    content = item.get("content") or content
                    tool_calls = item.get("tool_calls") or []

            if content or tool_calls:
                push({"role": "assistant", "content": content, "tool_calls": tool_calls})
            if content:
                yield {"type": "assistant", "content": content}

            if not tool_calls:
                # Fallback for small models: interpret an explicit "ACTION:" line.
                tool_calls = _fallback_action(content)
                if not tool_calls:
                    break

            for i, tc in enumerate(tool_calls):
                name = tc.get("name")
                args = tc.get("arguments") or {}
                yield {"type": "tool_call", "name": name, "arguments": args}

                result, actions = design.execute_tool(style, name, args)

                # Give the model a compact, serialisable result to read back.
                # Layer-lookup results carry the full list of real ids so the
                # model can self-correct, so keep this cap comfortably above that.
                result_text = json.dumps(result)
                if len(result_text) > 12000:
                    result_text = result_text[:12000] + "…(truncated)"
                push({
                    "role": "tool",
                    "name": name,
                    "tool_call_id": tc.get("id") or f"call_{step}_{i}",
                    "content": result_text,
                })
                yield {"type": "tool_result", "name": name,
                       "result": result, "actions": actions}
    except llm.LLMError as exc:
        yield {"type": "error", "message": str(exc)}
        return
    except Exception as exc:  # pragma: no cover - unexpected
        yield {"type": "error", "message": f"{type(exc).__name__}: {exc}"}
        return

    yield {
        "type": "done",
        "overview": design.style_overview(style),
        "style": json.loads(json.dumps(style)),
    }
