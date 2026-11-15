import pytest

from app.core.config import config_manager
from app.services import agent_service, llm_providers

TOOL = {"type": "function", "function": {"name": "lookup", "description": "d",
        "parameters": {"type": "object", "properties": {"q": {"type": "string"}}}}}
CALL = {"id": "c1", "type": "function", "function": {"name": "lookup", "arguments": '{"q": "x"}'}}
CONVERSATION = [
    {"role": "system", "content": "be brief"},
    {"role": "user", "content": "hi"},
]


@pytest.fixture
def http(monkeypatch):
    sent = []
    replies = []

    def fake(method, url, body=None):
        sent.append((method, url, body))
        return replies.pop(0)

    monkeypatch.setattr(llm_providers, "_http", fake)
    monkeypatch.setattr(config_manager.config, "ollama_url", "http://localhost:11434")
    return sent, replies


def test_ollama_chat_uses_openai_endpoint_and_returns_tool_calls(http):
    sent, replies = http
    replies.append({"choices": [{"message": {"content": "hello", "tool_calls": [CALL]}}]})
    out = llm_providers.chat("ollama", "llama3.2", CONVERSATION, [TOOL], 50)
    method, url, body = sent[0]
    assert (method, url) == ("POST", "http://localhost:11434/v1/chat/completions")
    assert body["model"] == "llama3.2" and body["max_tokens"] == 50 and body["tools"] == [TOOL]
    assert "chat_template_kwargs" not in body
    assert out == {"content": "hello", "tool_calls": [CALL]}


def test_ollama_lists_installed_models_sorted(http):
    sent, replies = http
    replies.append({"models": [{"name": "b"}, {"name": "a"}]})
    assert llm_providers.list_models("ollama") == ["a", "b"]
    assert sent[0][1] == "http://localhost:11434/api/tags"


def test_ollama_address_must_be_http(monkeypatch):
    monkeypatch.setattr(config_manager.config, "ollama_url", "file:///etc/passwd")
    with pytest.raises(RuntimeError, match="http"):
        llm_providers.list_models("ollama")


def test_unreachable_ollama_says_how_to_fix_it(monkeypatch):
    monkeypatch.setattr(config_manager.config, "ollama_url", "http://127.0.0.1:1")
    with pytest.raises(RuntimeError, match="Start Ollama"):
        llm_providers.list_models("ollama")


def test_reply_runs_tool_loop_through_ollama(monkeypatch):
    calls = []

    def fake_chat(provider, model, messages, tools, max_tokens):
        calls.append((provider, model, [m["role"] for m in messages]))
        return {"content": "", "tool_calls": [CALL]} if len(calls) == 1 else {"content": " final ", "tool_calls": []}

    class Session:
        def call_tool(self, name, args):
            return f"{name}:{args}"

    monkeypatch.setattr(llm_providers, "chat", fake_chat)
    monkeypatch.setattr(agent_service, "_llm_url", lambda *_: pytest.fail("local server must stay off"))
    monkeypatch.setattr(agent_service, "_open_tools", lambda servers: ([TOOL], {"lookup": (Session(), "lookup")}))
    text = agent_service.reply("sys", [{"role": "user", "content": "hi"}], [{}], "llama3.2", "ollama")
    assert text == "final"
    assert calls[1] == ("ollama", "llama3.2", ["system", "user", "assistant", "tool"])


def test_agent_model_must_match_provider():
    from pydantic import ValidationError

    from app.api.routes.agents import AgentIn

    base = {"name": "a", "system_prompt": "p"}
    assert AgentIn(**base).llm_provider == "local"
    assert AgentIn(**base, llm_provider="ollama", llm_model="llama3.2:latest").llm_model == "llama3.2:latest"
    with pytest.raises(ValidationError):
        AgentIn(**base, llm_provider="ollama", llm_model="agent-llm")
    with pytest.raises(ValidationError):
        AgentIn(**base, llm_provider="local", llm_model="llama3.2")
    with pytest.raises(ValidationError):
        AgentIn(**base, llm_provider="openai", llm_model="gpt-x")
