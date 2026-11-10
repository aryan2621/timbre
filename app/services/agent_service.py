from __future__ import annotations

import io
import json
import urllib.request
import uuid
from collections.abc import Sequence

import soundfile as sf

from app.core.config import config_manager
from app.data.model_catalog import get_model, is_model_present, model_local_path
from app.runtimes.native import NativeServer
from app.services.mcp_client import McpError, McpSession

WHISPER_RATE = 16000
DEFAULT_LLM = "agent-llm"
LLM_CONTEXT = 8192
MAX_REPLY_TOKENS = 400
MAX_TOOL_ROUNDS = 4
SPOKEN_STYLE = "Reply in one to three short spoken sentences. No lists, markdown or emoji."

llm_server = NativeServer("llama-server", "language")
whisper_server = NativeServer("whisper-server", "speech recognition", ready_path="/")


class AgentModelsMissing(RuntimeError):
    pass


def _model_file(model_id: str) -> str:
    model = get_model(model_id)
    models_dir = config_manager.get_models_directory()
    if model is None or not is_model_present(model, models_dir):
        raise AgentModelsMissing(f"Download {model.name if model else model_id} from the Models page first.")
    return str(model_local_path(model, models_dir) / model.files[0].name)


def _wav_16k(audio: bytes) -> bytes:
    samples, rate = sf.read(io.BytesIO(audio), dtype="float32", always_2d=True)
    import librosa

    mono = librosa.resample(samples.mean(axis=1), orig_sr=rate, target_sr=WHISPER_RATE)
    buffer = io.BytesIO()
    sf.write(buffer, mono, WHISPER_RATE, format="WAV", subtype="PCM_16")
    return buffer.getvalue()


WHISPER_PREFERENCE = ("agent-whisper-large-v3-turbo", "agent-whisper-small", "agent-whisper", "agent-whisper-tiny")


def _installed_whisper() -> str:
    models_dir = config_manager.get_models_directory()
    for model_id in WHISPER_PREFERENCE:
        model = get_model(model_id)
        if model is not None and is_model_present(model, models_dir):
            return model_id
    return "agent-whisper"


def _whisper_url() -> str:
    whisper_server.stop_if_idle()
    return whisper_server.ensure(["--model", _model_file(_installed_whisper())])


def _llm_url(model_id: str = DEFAULT_LLM) -> str:
    llm_server.stop_if_idle()
    return llm_server.ensure([
        "--model", _model_file(model_id), "--ctx-size", str(LLM_CONTEXT),
        "--n-gpu-layers", "999", "--parallel", "1", "--jinja",
    ])


def warm() -> None:
    for start in (_whisper_url, _llm_url):
        try:
            start()
        except (AgentModelsMissing, RuntimeError):
            return


def transcribe(audio: bytes) -> str:
    url = _whisper_url()
    boundary = uuid.uuid4().hex
    parts = (
        f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="audio.wav"\r\n'
        f"Content-Type: audio/wav\r\n\r\n"
    ).encode() + _wav_16k(audio) + (
        f'\r\n--{boundary}\r\nContent-Disposition: form-data; name="response_format"\r\n\r\njson\r\n--{boundary}--\r\n'
    ).encode()
    request = urllib.request.Request(
        url + "/inference", data=parts, headers={"Content-Type": f"multipart/form-data; boundary={boundary}"}
    )
    return str(whisper_server.send(request).get("text", "")).strip()


def _open_tools(servers: Sequence[dict[str, str]]) -> tuple[list[dict], dict[str, tuple[McpSession, str]]]:
    specs: list[dict] = []
    routes: dict[str, tuple[McpSession, str]] = {}
    for index, server in enumerate(servers):
        try:
            session = McpSession(server["url"], server.get("token", "")).open()
            tools = session.list_tools()
        except McpError:
            continue
        for tool in tools:
            alias = f"s{index}__{tool['name']}"
            routes[alias] = (session, tool["name"])
            specs.append({"type": "function", "function": {
                "name": alias,
                "description": tool.get("description", ""),
                "parameters": tool.get("inputSchema") or {"type": "object", "properties": {}},
            }})
    return specs, routes


def _run_tool(routes: dict[str, tuple[McpSession, str]], call: dict) -> str:
    session, name = routes.get(call["function"]["name"], (None, ""))
    if session is None:
        return "Unknown tool."
    try:
        return session.call_tool(name, json.loads(call["function"].get("arguments") or "{}"))
    except (McpError, json.JSONDecodeError) as exc:
        return f"Tool error: {exc}"


def reply(
    system_prompt: str,
    messages: Sequence[dict[str, str]],
    servers: Sequence[dict[str, str]] = (),
    llm_model: str = DEFAULT_LLM,
) -> str:
    _llm_url(llm_model)
    specs, routes = _open_tools(servers)
    conversation: list[dict] = [{"role": "system", "content": f"{system_prompt}\n\n{SPOKEN_STYLE}"}, *messages]
    for round_number in range(MAX_TOOL_ROUNDS + 1):
        if round_number == MAX_TOOL_ROUNDS:
            specs = []
        body: dict = {
            "messages": conversation,
            "temperature": 0.7,
            "max_tokens": MAX_REPLY_TOKENS,
            "chat_template_kwargs": {"enable_thinking": False},
        }
        if specs:
            body["tools"] = specs
        message = llm_server.request("/v1/chat/completions", body)["choices"][0]["message"]
        calls = message.get("tool_calls") or []
        if not calls or not specs:
            return str(message.get("content") or "").strip()
        conversation.append({"role": "assistant", "content": message.get("content") or "", "tool_calls": calls})
        for call in calls:
            conversation.append({"role": "tool", "tool_call_id": call.get("id", ""), "content": _run_tool(routes, call)})
    return ""


def stop_all() -> None:
    llm_server.stop()
    whisper_server.stop()
