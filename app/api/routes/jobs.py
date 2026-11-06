"""
Synthesis job HTTP routes (status, cancel, audio).
"""

import os
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.services.synthesis_service import job_manager

router = APIRouter()


@router.get("/api/jobs/{job_id}")
def get_job(job_id: str) -> dict[str, Any]:
    job = job_manager.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job.to_dict()


@router.post("/api/jobs/{job_id}/cancel")
def cancel_job(job_id: str) -> dict[str, Any]:
    job = job_manager.cancel(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job.to_dict()


@router.get("/api/jobs/{job_id}/audio")
def job_audio(job_id: str) -> FileResponse:
    job = job_manager.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.state != "done" or not job.audio_path or not os.path.exists(job.audio_path):
        raise HTTPException(status_code=404, detail="Job audio is not ready")
    return FileResponse(job.audio_path)
