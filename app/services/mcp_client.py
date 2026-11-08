from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse

PROTOCOL_VERSION = "2025-03-26"
TIMEOUT_SECONDS = 30
MAX_RESULT_CHARS = 4000


class McpError(RuntimeError):
    pass


def validate_url(url: str) -> str:
    parsed = urlparse(url.strip())
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise ValueError("MCP server URL must start with http:// or https://")
    return url.strip()


def _decode(raw: bytes, content_type: str) -> dict[str, Any]:
    text = raw.decode("utf-8", "replace")
    if "text/event-stream" in content_type:
        payloads = [line[5:].strip() for line in text.splitlines() if line.startswith("data:")]
        text = next((p for p in reversed(payloads) if p), "")
    return json.loads(text) if text else {}


@dataclass
class McpSession:
    url: str
    token: str = ""
    session_id: str = ""
    _next_id: int = field(default=0, repr=False)

    def _post(self, body: dict[str, Any]) -> dict[str, Any]:
        headers = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        if self.session_id:
            headers["Mcp-Session-Id"] = self.session_id
        request = urllib.request.Request(self.url, data=json.dumps(body).encode(), headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
                self.session_id = response.headers.get("Mcp-Session-Id") or self.session_id
                return _decode(response.read(), response.headers.get("Content-Type", ""))
        except urllib.error.HTTPError as exc:
            raise McpError(f"{self.url} answered {exc.code}") from exc
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise McpError(f"Could not reach {self.url}: {exc}") from exc

    def _call(self, method: str, params: dict[str, Any] | None = None) -> Any:
        self._next_id += 1
        reply = self._post({"jsonrpc": "2.0", "id": self._next_id, "method": method, "params": params or {}})
        if "error" in reply:
            raise McpError(str(reply["error"].get("message", reply["error"])))
        return reply.get("result", {})

    def open(self) -> McpSession:
        self._call("initialize", {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {},
            "clientInfo": {"name": "timbre", "version": "1.0"},
        })
        self._post({"jsonrpc": "2.0", "method": "notifications/initialized"})
        return self

    def list_tools(self) -> list[dict[str, Any]]:
        return list(self._call("tools/list").get("tools", []))

    def call_tool(self, name: str, arguments: dict[str, Any]) -> str:
        result = self._call("tools/call", {"name": name, "arguments": arguments})
        text = "\n".join(part.get("text", "") for part in result.get("content", []) if part.get("type") == "text")
        return (f"Tool error: {text}" if result.get("isError") else text)[:MAX_RESULT_CHARS]


def test_server(url: str, token: str = "") -> list[str]:
    return [tool["name"] for tool in McpSession(validate_url(url), token).open().list_tools()]
