"""
Synthesis orchestration HTTP routes (single render + job lifecycle).
"""

from typing import Any

from fastapi import APIRouter, HTTPException

from app.api.routes._common import build_params, resolve_engine
from app.api.schemas import SynthesisRequest
from app.data.voice_repo import voice_repo
from app.services.synthesis_service import RenderBusy, job_manager

router = APIRouter()


@router.post("/api/synthesize")
def synthesize(payload: SynthesisRequest) -> dict[str, Any]:
    text = payload.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Text is empty")

    profile = voice_repo.get_profile_by_id(payload.voice_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Voice profile not found")

    engine = resolve_engine(payload.engine_name)
    try:
        job = job_manager.create(
            engine=engine,
            profile=profile,
            text=text,
            params=build_params(payload.params),
            sentence_pause_ms=payload.sentence_pause_ms,
        )
    except RenderBusy as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return job.to_dict()
