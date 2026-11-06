"""
Download-manager HTTP routes.
"""

from typing import Any

from fastapi import APIRouter, HTTPException

from app.api.downloads import download_manager

router = APIRouter()


@router.get("/api/downloads/{job_id}")
def get_download(job_id: str) -> dict[str, Any]:
    job = download_manager.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Download job not found")
    return job.to_dict()


@router.post("/api/downloads/{job_id}/cancel")
def cancel_download(job_id: str) -> dict[str, Any]:
    job = download_manager.cancel(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Download job not found")
    return job.to_dict()
