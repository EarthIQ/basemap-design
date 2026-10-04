"""LLM provider adapters with tool calling and token streaming.

Two providers, both using OpenAI-style function schemas:

  * ``ollama``            - local, via ``/api/chat`` (NDJSON stream)
  * ``openai_compatible`` - any ``/chat/completions`` endpoint (OpenAI,
                            OpenRouter, Groq, Together, LM Studio, ...)

Streaming interface
-------------------
``stream_chat(config, messages, tools)`` is a generator that yields a small,
provider-agnostic protocol so the agent can push text to the UI token-by-token:

  * ``{"type": "delta", "text": str}``
    ``{"type": "message", "content": str,
     "tool_calls": [{id, name, arguments}, ...]}``

``chat(...)`` is a thin non-streaming wrapper over ``stream_chat`` for callers
that only need the finished message. The unified message list has roles
``user`` / ``assistant`` / ``tool``; assistant messages may carry
``tool_calls`` and ``tool`` messages carry the string result plus
``tool_call_id``.
"""
from __future__ import annotations

import json
from typing import Any, Iterator

import httpx

from . import settings


class LLMError(RuntimeError):
    """Raised for any provider/network/protocol failure we can report."""


class _Client:
    """A lazily-created, shared httpx client with sane timeouts."""

    _inst: httpx.Client | None = None

    @classmethod
    def client(cls) -> httpx.Client:
        if cls._inst is None:
            cls._inst = httpx.Client(
                timeout=httpx.Timeout(settings.LLM_TIMEOUT, connect=10.0),
                headers={"User-Agent": "earthiq/0.2 (+base-map-designer)"},
            )
        return cls._inst


def _ollama_wire(messages: list[dict]) -> list[dict]:
    wire = []
    for m in messages:
        role = m["role"]
        if role == "assistant" and m.get("tool_calls"):
            wire.append({
                "role": "assistant",
                "content": m.get("content") or "",
                "tool_calls": [
                    {"function": {"name": tc["name"], "arguments": tc["arguments"]}}
                    for tc in m["tool_calls"] if tc.get("name")
                ],
            })
        elif role == "tool":
            wire.append({"role": "tool", "content": m.get("content") or ""})
        else:
            wire.append({"role": role, "content": m.get("content") or ""})
    return wire


def _openai_wire(messages: list[dict]) -> list[dict]:
    wire = []
    for m in messages:
        role = m["role"]
        if role == "assistant" and m.get("tool_calls"):
            wire.append({
                "role": "assistant",
                "content": m.get("content") or None,
                "tool_calls": [
                    {
                        "id": tc.get("id") or f"call_{i}",
                        "type": "function",
                        "function": {
                            "name": tc["name"],
                            "arguments": json.dumps(tc.get("arguments") or {}),
                        },
                    }
                    for i, tc in enumerate(m["tool_calls"]) if tc.get("name")
                ],
            })
        elif role == "tool":
            wire.append({
                "role": "tool",
                "tool_call_id": m.get("tool_call_id") or "call_0",
                "content": m.get("content") or "",
            })
        else:
            wire.append({"role": role, "content": m.get("content") or ""})
    return wire


def _merge_ollama_tool(tool_map: dict, tc: dict) -> None:
    fn = tc.get("function") or {}
    idx = fn.get("index")
    if idx is None:
        idx = 0 if not tool_map else len(tool_map)
    entry = tool_map.setdefault(idx, {"id": tc.get("id"), "name": None,
                                      "args": {}, "args_str": ""})
    if tc.get("id"):
        entry["id"] = tc["id"]
    if fn.get("name"):
        entry["name"] = fn["name"]
    arg = fn.get("arguments")
    if isinstance(arg, dict):
        entry["args"].update(arg)
    elif isinstance(arg, str) and arg:
        entry["args_str"] += arg


def _finalize_ollama_tools(tool_map: dict) -> list[dict[str, Any]]:
    out = []
    for idx in sorted(tool_map):
        e = tool_map[idx]
        args = e["args"]
        if not args and e.get("args_str"):
            try:
                args = json.loads(e["args_str"])
            except Exception:
                args = {}
        out.append({
            "id": e["id"] or f"call_{idx}",
            "name": e["name"],
            "arguments": args if isinstance(args, dict) else {},
        })
    return out


def _merge_openai_tool(tool_map: dict, tc: dict) -> None:
    idx = tc.get("index", 0)
    entry = tool_map.setdefault(idx, {"id": "", "name": None, "args_str": ""})
    if tc.get("id"):
        entry["id"] = tc["id"]
    fn = tc.get("function") or {}
    if fn.get("name"):
        entry["name"] = fn["name"]
    arg = fn.get("arguments")
    if isinstance(arg, str):
        entry["args_str"] += arg


def _finalize_openai_tools(tool_map: dict) -> list[dict[str, Any]]:
    out = []
    for idx in sorted(tool_map):
        e = tool_map[idx]
        args = {}
        if e.get("args_str"):
            try:
                args = json.loads(e["args_str"])
            except Exception:
                args = {}
        out.append({
            "id": e["id"] or f"call_{idx}",
            "name": e["name"],
            "arguments": args if isinstance(args, dict) else {},
        })
    return out


def _read_stream(resp) -> Iterator[str]:
    """Yield non-empty body lines from an httpx streaming response."""
    for line in resp.iter_lines():
        if line:
            yield line


# ---------------------------------------------------------------------------
# Ollama (NDJSON)
# ---------------------------------------------------------------------------
def _stream_ollama(config: dict, messages: list[dict], tools: list[dict]) -> Iterator[dict]:
    base = (config.get("baseUrl") or settings.OLLAMA_BASE_URL).rstrip("/")
    model = config.get("model") or settings.DEFAULT_OLLAMA_MODEL
    payload: dict[str, Any] = {
        "model": model,
        "messages": _ollama_wire(messages),
        "stream": True,
    }
    if tools:
        payload["tools"] = tools

    content_parts: list[str] = []
    tool_map: dict[int, dict] = {}

    try:
        with _Client.client().stream("POST", f"{base}/api/chat", json=payload) as resp:
            if resp.status_code >= 400:
                body = resp.read().decode("utf-8", "replace")
                raise LLMError(f"Ollama {resp.status_code}: {body[:500]}")
            for line in _read_stream(resp):
                try:
                    chunk = json.loads(line)
                except json.JSONDecodeError:
                    continue
                msg = chunk.get("message") or {}

                if msg.get("content"):
                    text = msg["content"]
                    content_parts.append(text)
                    yield {"type": "delta", "text": text}

                for tc in msg.get("tool_calls") or []:
                    _merge_ollama_tool(tool_map, tc)

                if chunk.get("done"):
                    break
    except LLMError:
        raise
    except httpx.HTTPError as exc:
        raise LLMError(f"Could not reach Ollama at {base}: {exc}") from exc

    yield {
        "type": "message",
        "content": "".join(content_parts).strip(),
        "tool_calls": _finalize_ollama_tools(tool_map),
    }


# ---------------------------------------------------------------------------
# OpenAI-compatible (SSE)
# ---------------------------------------------------------------------------
def _stream_openai(config: dict, messages: list[dict], tools: list[dict]) -> Iterator[dict]:
    base = (config.get("baseUrl") or settings.OPENAI_BASE_URL).rstrip("/")
    model = config.get("model") or settings.OPENAI_MODEL
    api_key = config.get("apiKey") or settings.OPENAI_API_KEY
    if not api_key:
        raise LLMError("No API key set for the OpenAI-compatible provider. "
                       "Add one in Settings (top-right gear).")

    url = base if base.endswith("/chat/completions") else f"{base}/chat/completions"
    payload: dict[str, Any] = {"model": model, "messages": _openai_wire(messages), "stream": True}
    if tools:
        payload["tools"] = tools
        payload["tool_choice"] = "auto"

    headers = {"Authorization": f"Bearer {api_key}"}
    content_parts: list[str] = []
    tool_map: dict[int, dict] = {}

    try:
        with _Client.client().stream("POST", url, json=payload, headers=headers) as resp:
            if resp.status_code >= 400:
                body = resp.read().decode("utf-8", "replace")
                raise LLMError(f"OpenAI-compatible {resp.status_code}: {body[:500]}")
            for line in _read_stream(resp):
                s = line.strip()
                if not s.startswith("data:"):
                    continue
                data = s[len("data:"):].strip()
                if data == "[DONE]":
                    break
                try:
                    chunk = json.loads(data)
                except json.JSONDecodeError:
                    continue
                choices = chunk.get("choices") or []
                if not choices:
                    continue
                delta = choices[0].get("delta") or {}

                if delta.get("content"):
                    text = delta["content"]
                    content_parts.append(text)
                    yield {"type": "delta", "text": text}

                for tc in delta.get("tool_calls") or []:
                    _merge_openai_tool(tool_map, tc)
    except LLMError:
        raise
    except httpx.HTTPError as exc:
        raise LLMError(f"Could not reach {url}: {exc}") from exc

    yield {
        "type": "message",
        "content": "".join(content_parts).strip(),
        "tool_calls": _finalize_openai_tools(tool_map),
    }


# ---------------------------------------------------------------------------
# Public dispatcher + helpers
# ---------------------------------------------------------------------------
def stream_chat(config: dict, messages: list[dict], tools: list[dict]) -> Iterator[dict]:
    """Stream one assistant turn. See module docstring for the event protocol."""
    provider = (config.get("provider") or "ollama").lower()
    if provider == "ollama":
        yield from _stream_ollama(config, messages, tools)
    else:
        yield from _stream_openai(config, messages, tools)


def chat(config: dict, messages: list[dict], tools: list[dict]) -> dict:
    """Non-streaming convenience wrapper: returns the finished message."""
    content = ""
    tool_calls: list[dict] = []
    for item in stream_chat(config, messages, tools):
        if item["type"] == "delta":
            content += item["text"]
        else:
            content = item.get("content") or content
            tool_calls = item.get("tool_calls") or []
    return {"content": content, "tool_calls": tool_calls}


def list_models(config: dict) -> list[str]:
    """Best-effort list of model names for the configured provider."""
    provider = (config.get("provider") or "ollama").lower()
    if provider == "ollama":
        base = (config.get("baseUrl") or settings.OLLAMA_BASE_URL).rstrip("/")
        try:
            r = _Client.client().get(f"{base}/api/tags", timeout=8.0)
            if r.status_code < 400:
                return [m["name"] for m in r.json().get("models", []) if m.get("name")]
        except Exception:
            pass
        return []

    base = (config.get("baseUrl") or settings.OPENAI_BASE_URL).rstrip("/")
    api_key = config.get("apiKey") or settings.OPENAI_API_KEY
    if not api_key:
        return []
    url = base if base.endswith("/models") else f"{base}/models"
    try:
        r = _Client.client().get(url, headers={"Authorization": f"Bearer {api_key}"},
                                 timeout=10.0)
        if r.status_code < 400:
            data = r.json()
            items = data.get("data") or data.get("models") or []
            return [m.get("id") or m.get("name") for m in items if (m.get("id") or m.get("name"))]
    except Exception:
        pass
    return []


def check_ollama(base_url: str | None = None) -> dict:
    base = (base_url or settings.OLLAMA_BASE_URL).rstrip("/")
    out: dict[str, Any] = {"ok": False, "baseUrl": base, "models": []}
    try:
        r = _Client.client().get(f"{base}/api/version", timeout=8.0)
        if r.status_code < 400:
            out["ok"] = True
            out["version"] = r.json().get("version")
    except Exception:
        pass
    try:
        r = _Client.client().get(f"{base}/api/tags", timeout=8.0)
        if r.status_code < 400:
            out["models"] = [m.get("name") for m in r.json().get("models", [])]
    except Exception:
        pass
    return out
