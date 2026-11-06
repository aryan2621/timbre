"""
Batch orchestration HTTP routes (queue + job lifecycle).
"""

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException

from app.api.routes._common import build_params, resolve_engine
from app.api.schemas import BatchRequest
from app.core.logging_setup import get_logger
from app.data.voice_repo import voice_repo
from app.services.synthesis_service import BatchItemState, RenderBusy, batch_manager

router = APIRouter()
logger = get_logger("batch")


def _safe_filename(raw: str | None, default_stem: str) -> str:
    """A bare '<name>.wav': no folders, no '..', no hidden files."""
    stem = Path((raw or "").replace("\\", "/")).stem.strip().lstrip(".")
    return f"{stem or default_stem}.wav"


@router.post("/api/batch")
def start_batch(payload: BatchRequest) -> dict[str, Any]:
    """Queues a whole script file: one rendered file per line."""
    lines = [item for item in payload.items if item.text.strip()]
    if not lines:
        raise HTTPException(status_code=400, detail="The batch queue is empty")

    profile = voice_repo.get_profile_by_id(payload.voice_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Voice profile not found")

    engine = resolve_engine(payload.engine_name)
    params = build_params(payload.params)

    items = []
    used: set[str] = set()
    for index, line in enumerate(lines):
        filename = _safe_filename(line.filename, f"line_{index + 1:04d}")
        base, counter = filename, 2
        while filename.lower() in used:
            filename = f"{Path(base).stem}_{counter}.wav"
            counter += 1
        used.add(filename.lower())
        items.append(BatchItemState(index=index, filename=filename, text=line.text.strip()))

    try:
        job = batch_manager.create(
            engine=engine,
            profile=profile,
            items=items,
            params=params,
            sentence_pause_ms=payload.sentence_pause_ms,
            output_dir=payload.output_dir,
        )
    except RenderBusy as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
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
