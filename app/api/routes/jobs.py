"""
Synthesis job HTTP routes (status, cancel, audio).
"""

import os
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, Response

from app.services.sound_service import sound_manager
from app.services.synthesis_service import job_manager

router = APIRouter()


def _find_job(job_id: str):
    for manager in (job_manager, sound_manager):
        job = manager.get(job_id)
        if job is not None:
            return manager, job
    return None, None


@router.get("/api/jobs/{job_id}")
def get_job(job_id: str) -> dict[str, Any]:
    _, job = _find_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job.to_dict()


@router.post("/api/jobs/{job_id}/cancel")
def cancel_job(job_id: str) -> dict[str, Any]:
    manager, _ = _find_job(job_id)
    job = manager.cancel(job_id) if manager else None
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job.to_dict()


@router.get("/api/jobs/{job_id}/audio")
def job_audio(job_id: str) -> FileResponse:
    _, job = _find_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.state != "done" or not job.audio_path or not os.path.exists(job.audio_path):
        raise HTTPException(status_code=404, detail="Job audio is not ready")
    return FileResponse(job.audio_path)


@router.get("/api/jobs/{job_id}/chunks/{index}")
def job_chunk(job_id: str, index: int) -> Response:
    """One finished chunk as WAV, so the UI can play while the rest renders."""
    job = job_manager.get(job_id)
    chunks = job.live_chunks if job is not None else []
    if job is None or not 0 <= index < len(chunks):
        raise HTTPException(status_code=404, detail="Chunk is not ready")
    return Response(content=chunks[index], media_type="audio/wav")
