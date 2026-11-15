"""Chat providers for agents besides the bundled llama.cpp: Ollama, over its OpenAI-compatible API.
Takes and returns OpenAI-shaped messages and tool calls, so the tool loop in agent_service.reply is the
same whichever one answers. Plain urllib."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any
from urllib.parse import urlparse

from app.core.config import config_manager

LOCAL = "local"
REMOTE = ("ollama",)
TIMEOUT = 120


def _http(method: str, url: str, body: dict | None = None) -> dict[str, Any]:
    request = urllib.request.Request(
        url, data=None if body is None else json.dumps(body).encode(), method=method,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:  # noqa: S310 - http(s) checked in _base_url
            return json.loads(response.read())
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"Ollama: {_error_text(exc)}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError("Ollama returned an unexpected reply.") from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise RuntimeError(
            f"Ollama is not running at {urlparse(url).netloc}. Start Ollama and pull a model (e.g. ollama pull llama3.2)."
        ) from exc


def _error_text(exc: urllib.error.HTTPError) -> str:
    try:
        error = json.loads(exc.read()).get("error", {})
        return str(error.get("message") if isinstance(error, dict) else error) or f"HTTP {exc.code}"
    except (ValueError, AttributeError):
        return f"HTTP {exc.code}"


def _base_url() -> str:
    url = config_manager.config.ollama_url.rstrip("/")
    if urlparse(url).scheme not in ("http", "https"):
        raise RuntimeError("The Ollama address must start with http:// or https://")
    return url


def list_models(provider: str) -> list[str]:
    """Models installed in Ollama; also how the UI tells whether Ollama is running."""
    try:
        return sorted(item["name"] for item in _http("GET", _base_url() + "/api/tags").get("models", []))
    except (KeyError, TypeError, AttributeError) as exc:
        raise RuntimeError("Ollama returned an unexpected reply.") from exc


def chat(provider: str, model: str, messages: list[dict], tools: list[dict], max_tokens: int) -> dict[str, Any]:
    """One round trip. Returns {"content": str, "tool_calls": [OpenAI-shaped calls]}."""
    body: dict[str, Any] = {"model": model, "messages": messages, "max_tokens": max_tokens, "temperature": 0.7}
    if tools:
        body["tools"] = tools
    try:
        message = _http("POST", _base_url() + "/v1/chat/completions", body)["choices"][0]["message"]
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError("Ollama returned an unexpected reply.") from exc
    return {"content": message.get("content") or "", "tool_calls": message.get("tool_calls") or []}
