"""
History HTTP routes.
"""

import os
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.api.schemas import history_to_dict
from app.core.logging_setup import get_logger
from app.data.history_repo import history_repo
from app.services.synthesis_service import _PEAKS_CACHE, _PEAKS_CACHE_LIMIT, compute_peaks

router = APIRouter()
logger = get_logger("history")


@router.get("/api/history")
def list_history(q: str = "") -> list[dict[str, Any]]:
    entries = history_repo.search(q, limit=200) if q.strip() else history_repo.list_recent(200)
    return [history_to_dict(entry) for entry in entries]


@router.delete("/api/history/{entry_id}")
def delete_history(entry_id: int) -> dict[str, Any]:
    if not history_repo.delete_entry(entry_id):
        raise HTTPException(status_code=404, detail="History entry not found")
    return {"ok": True}


@router.delete("/api/history")
def clear_history() -> dict[str, Any]:
    return {"deleted": history_repo.clear_all()}


@router.get("/api/history/{entry_id}/audio")
def history_audio(entry_id: int) -> FileResponse:
    entry = history_repo.get_entry_by_id(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="History entry not found")
    if not entry.audio_path or not os.path.exists(entry.audio_path):
        raise HTTPException(status_code=404, detail="Rendered audio file is missing")
    return FileResponse(entry.audio_path)


@router.get("/api/history/{entry_id}/peaks")
def history_peaks(entry_id: int) -> dict[str, Any]:
    """Returns the waveform of a finished render.

    The History screen draws a mini waveform in every row. Computing it from
    the stored WAV is cheap, but decoding the same file on every hover is
    not, so the result is cached until the file changes.
    """
    entry = history_repo.get_entry_by_id(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="History entry not found")
    path = entry.audio_path
    if not path or not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Rendered audio file is missing")

    try:
        stat = os.stat(path)
    except OSError as exc:
        raise HTTPException(status_code=404, detail="Rendered audio file is missing") from exc

    key = os.path.abspath(path)
    cached = _PEAKS_CACHE.get(key)
    if cached and cached[0] == stat.st_mtime and cached[1] == stat.st_size:
        return {
            "id": entry_id,
            "peaks": cached[2],
            "duration_seconds": entry.duration_seconds,
            "sample_rate": entry.sample_rate,
        }

    peaks: list[float] = []
    try:
        import soundfile as sf

        audio, sample_rate = sf.read(path, dtype="float32", always_2d=False)
        peaks = compute_peaks(audio)
    except Exception as exc:  # noqa: BLE001 - a missing codec must not break the list
        logger.warning("Could not compute peaks for %s: %s", path, exc)
        peaks = []

    if len(_PEAKS_CACHE) >= _PEAKS_CACHE_LIMIT:
        _PEAKS_CACHE.clear()
    _PEAKS_CACHE[key] = (stat.st_mtime, stat.st_size, peaks)

    return {
        "id": entry_id,
        "peaks": peaks,
        "duration_seconds": entry.duration_seconds,
        "sample_rate": entry.sample_rate,
    }
