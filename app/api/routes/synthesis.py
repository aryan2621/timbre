"""
Synthesis orchestration HTTP routes (single render + job lifecycle).
"""

import random
from typing import Any

from fastapi import APIRouter, HTTPException

from app.api.schemas import SynthesisRequest
from app.data.voice_repo import voice_repo
from app.engines.base import SynthesisParameters
from app.engines.registry import engine_registry
from app.services.synthesis_service import job_manager

router = APIRouter()


@router.post("/api/synthesize")
def synthesize(payload: SynthesisRequest) -> dict[str, Any]:
    text = payload.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Text is empty")

    profile = voice_repo.get_profile_by_id(payload.voice_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Voice profile not found")

    engine = engine_registry.get_engine(payload.engine_name)
    if engine is None:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown engine '{payload.engine_name}'. Available: {', '.join(engine_registry.list_engine_names())}",
        )
    if not engine.is_available():
        raise HTTPException(
            status_code=409,
            detail=f"The {engine.name} weights are not downloaded on this machine",
        )

    params = SynthesisParameters(
        temperature=payload.params.temperature,
        cfg_weight=payload.params.cfg_weight,
        exaggeration=payload.params.exaggeration,
        speed=payload.params.speed,
        seed=payload.params.seed,
        top_p=payload.params.top_p,
        repetition_penalty=payload.params.repetition_penalty,
        language=payload.params.language,
        enable_watermark=payload.params.enable_watermark,
    )
    if params.seed < 0:
        params.seed = random.randint(1, 99_999_999)

    job = job_manager.create(
        engine=engine,
        profile=profile,
        text=text,
        params=params,
        sentence_pause_ms=payload.sentence_pause_ms,
    )
    return job.to_dict()
