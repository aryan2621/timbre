import random
from typing import Any

from fastapi import APIRouter, HTTPException

from app.api.schemas import SoundRequest, sound_engine_to_dict
from app.engines.base import SoundParameters
from app.engines.registry import sound_registry
from app.services.sound_service import sound_manager
from app.services.synthesis_service import RenderBusy

router = APIRouter()


@router.get("/api/sounds/engines")
def list_sound_engines() -> list[dict[str, Any]]:
    return [sound_engine_to_dict(engine) for engine in sound_registry.get_all_engines()]


@router.post("/api/sounds")
def generate_sound(payload: SoundRequest) -> dict[str, Any]:
    prompt = payload.prompt.strip()
    if not prompt:
        raise HTTPException(status_code=400, detail="Prompt is empty")

    engine = sound_registry.get_engine(payload.engine_name)
    if engine is None:
        raise HTTPException(status_code=400, detail=f"Unknown sound engine '{payload.engine_name}'")

    if payload.kind not in engine.kinds:
        raise HTTPException(status_code=400, detail=f"{engine.name} can't make {payload.kind}.")
    if payload.params.duration_seconds > engine.max_duration_seconds:
        raise HTTPException(
            status_code=400,
            detail=f"{engine.name} makes at most {engine.max_duration_seconds:g} seconds.",
        )
    reason = engine.unavailable_reason()
    if reason:
        raise HTTPException(status_code=409, detail=f"{engine.name} can't run here: {reason}")
    params = SoundParameters(**payload.params.model_dump())
    if params.seed < 0:
        params.seed = random.randint(1, 99_999_999)
    try:
        job = sound_manager.create(engine, prompt, payload.kind, params)
    except RenderBusy as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return job.to_dict()
