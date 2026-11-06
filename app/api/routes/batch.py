"""
Batch orchestration HTTP routes (queue + job lifecycle).
"""

import random
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException

from app.api.schemas import BatchRequest
from app.core.logging_setup import get_logger
from app.data.voice_repo import voice_repo
from app.engines.base import SynthesisParameters
from app.engines.registry import engine_registry
from app.services.synthesis_service import BatchItemState, batch_manager

router = APIRouter()
logger = get_logger("batch")


@router.post("/api/batch")
def start_batch(payload: BatchRequest) -> dict[str, Any]:
    """Queues a whole script file: one rendered file per line."""
    lines = [item for item in payload.items if item.text.strip()]
    if not lines:
        raise HTTPException(status_code=400, detail="The batch queue is empty")

    profile = voice_repo.get_profile_by_id(payload.voice_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Voice profile not found")

    engine = engine_registry.get_engine(payload.engine_name)
    if engine is None:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unknown engine '{payload.engine_name}'. "
                f"Available: {', '.join(engine_registry.list_engine_names())}"
            ),
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

    items = []
    for index, line in enumerate(lines):
        filename = (line.filename or "").strip() or f"line_{index + 1:04d}.wav"
        if not filename.lower().endswith(".wav"):
            filename = f"{Path(filename).stem}.wav"
        items.append(
            BatchItemState(index=index, filename=filename, text=line.text.strip())
        )

    job = batch_manager.create(
        engine=engine,
        profile=profile,
        items=items,
        params=params,
        sentence_pause_ms=payload.sentence_pause_ms,
        output_dir=payload.output_dir,
    )
    return job.to_dict()


@router.post("/api/batch/{job_id}/cancel")
def cancel_batch(job_id: str) -> dict[str, Any]:
    job = batch_manager.cancel(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Batch job not found")
    return job.to_dict()


@router.get("/api/batch/{job_id}")
def get_batch(job_id: str) -> dict[str, Any]:
    job = batch_manager.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Batch job not found")
    return job.to_dict()
