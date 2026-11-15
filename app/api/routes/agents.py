import re
import threading
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field, model_validator

from app.data.agent_repo import DuplicateAgent, agent_repo
from app.data.voice_repo import voice_repo
from app.runtimes.native import NativeUnavailable
from app.services import agent_service, llm_providers, mcp_client

router = APIRouter()


class McpServerIn(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    url: str = Field(max_length=500)
    token: str = Field("", max_length=500)


class McpTestIn(BaseModel):
    url: str = Field(max_length=500)
    token: str = Field("", max_length=500)


class AgentIn(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    voice_id: int | None = None
    system_prompt: str = Field(min_length=1, max_length=4000)
    icon: str = Field("bot", max_length=30)
    llm_provider: Literal["local", "ollama"] = "local"
    llm_model: str = Field("agent-llm", max_length=100, pattern=r"^[\w.:/-]+$")
    mcp_servers: list[McpServerIn] = Field(default_factory=list, max_length=8)

    @model_validator(mode="after")
    def _model_matches_provider(self):
        local_id = re.fullmatch(r"agent-llm[a-z0-9-]*", self.llm_model) is not None
        if (self.llm_provider == "local") != local_id:
            raise ValueError("Pick a model that belongs to the chosen provider.")
        return self


class Turn(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=4000)


class ReplyRequest(BaseModel):
    messages: list[Turn] = Field(min_length=1, max_length=40)


def _agent_or_404(agent_id: int) -> dict[str, Any]:
    agent = agent_repo.get(agent_id)
    if agent is None:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


def _public(agent: dict[str, Any]) -> dict[str, Any]:
    servers = [
        {"name": server["name"], "url": server["url"], "has_token": bool(server.get("token"))}
        for server in agent["mcp_servers"]
    ]
    return {**agent, "mcp_servers": servers}


def _run(call, *args):
    try:
        return call(*args)
    except (agent_service.AgentModelsMissing, NativeUnavailable) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.get("/api/agents")
def list_agents() -> list[dict[str, Any]]:
    return [_public(agent) for agent in agent_repo.list_all()]


@router.post("/api/agents")
def create_agent(payload: AgentIn) -> dict[str, Any]:
    if payload.voice_id is not None and voice_repo.get_profile_by_id(payload.voice_id) is None:
        raise HTTPException(status_code=404, detail="Voice profile not found")
    try:
        servers = [
            {**server.model_dump(), "url": mcp_client.validate_url(server.url)} for server in payload.mcp_servers
        ]
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    try:
        created = agent_repo.create(
            payload.name.strip(), payload.voice_id, payload.system_prompt.strip(), payload.icon, servers, payload.llm_model,
            payload.llm_provider,
        )
        return _public(created)
    except DuplicateAgent as exc:
        raise HTTPException(status_code=409, detail="An agent with that name already exists") from exc


@router.delete("/api/agents/{agent_id}")
def delete_agent(agent_id: int) -> dict[str, Any]:
    _agent_or_404(agent_id)
    agent_repo.delete(agent_id)
    return {"ok": True}


@router.post("/api/agents/mcp/test")
def test_mcp(payload: McpTestIn) -> dict[str, list[str]]:
    try:
        return {"tools": mcp_client.test_server(payload.url, payload.token)}
    except (ValueError, mcp_client.McpError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/api/agents/warm", status_code=202)
def warm_agents() -> dict[str, bool]:
    threading.Thread(target=agent_service.warm, daemon=True).start()
    return {"ok": True}


@router.post("/api/agents/transcribe")
async def transcribe(request: Request) -> dict[str, str]:
    audio = await request.body()
    if not audio:
        raise HTTPException(status_code=400, detail="No audio received")
    return {"text": _run(agent_service.transcribe, audio)}


@router.post("/api/agents/{agent_id}/reply")
def agent_reply(agent_id: int, payload: ReplyRequest) -> dict[str, str]:
    agent = _agent_or_404(agent_id)
    messages = [turn.model_dump() for turn in payload.messages]
    return {"text": _run(agent_service.reply, agent["system_prompt"], messages, agent["mcp_servers"], agent["llm_model"], agent["llm_provider"])}


@router.get("/api/llm/models")
def llm_models(provider: Literal["ollama"]) -> dict[str, list[str]]:
    return {"models": _run(llm_providers.list_models, provider)}
