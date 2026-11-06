"""
Voice HTTP routes.
"""

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse

from app.api.schemas import AUDIO_EXTENSIONS, VoiceCreateRequest, profile_to_dict
from app.core.logging_setup import get_logger
from app.data.models import VoiceProfile
from app.data.voice_repo import voice_repo
from app.services.voice_service import store_reference_audio

router = APIRouter()
logger = get_logger("voices")


@router.get("/api/voices")
def list_voices() -> list[dict[str, Any]]:
    return [profile_to_dict(profile) for profile in voice_repo.list_all_profiles()]


@router.get("/api/voices/{voice_id}")
def get_voice(voice_id: int) -> dict[str, Any]:
    profile = voice_repo.get_profile_by_id(voice_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Voice profile not found")
    return profile_to_dict(profile)


@router.post("/api/voices")
def create_voice(payload: VoiceCreateRequest) -> dict[str, Any]:
    name = payload.name.strip()
    if not name:
        raise HTTPException(status_code=400, detail="A voice name is required")
    if not payload.consent_confirmed:
        raise HTTPException(
            status_code=400,
            detail="Consent confirmation is required before creating a voice profile",
        )
    if voice_repo.get_profile_by_name(name) is not None:
        raise HTTPException(status_code=409, detail=f"A voice named '{name}' already exists")
    if not payload.reference_path.strip():
        raise HTTPException(
            status_code=400,
            detail="Reference audio is required to clone a voice",
        )

    source = Path(payload.reference_path).expanduser()
    if not source.is_file():
        raise HTTPException(status_code=400, detail=f"Reference audio not found: {source}")
    if source.suffix.lower() not in AUDIO_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported audio format '{source.suffix}'. Use WAV, FLAC, OGG or MP3.",
        )

    try:
        clip = store_reference_audio(source, name)
    except (ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    try:
        profile = voice_repo.create_profile(
            VoiceProfile(
                name=name,
                language=payload.language or "en",
                notes=payload.notes.strip(),
                consent_confirmed=True,
                clips=[clip],
            )
        )
    except Exception:
        if clip.file_path and Path(clip.file_path).exists():
            try:
                Path(clip.file_path).unlink(missing_ok=True)
            except OSError:
                logger.debug("Could not remove orphaned clip %s", clip.file_path)
        raise

    if profile is None:  # pragma: no cover - repository always returns the stored row
        raise HTTPException(status_code=500, detail="Could not store the voice profile")
    return profile_to_dict(profile)


@router.delete("/api/voices/{voice_id}")
def delete_voice(voice_id: int) -> dict[str, Any]:
    if not voice_repo.delete_profile(voice_id):
        raise HTTPException(status_code=404, detail="Voice profile not found")
    return {"ok": True}


@router.get("/api/voices/{voice_id}/clip")
def voice_clip(voice_id: int):
    profile = voice_repo.get_profile_by_id(voice_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Voice profile not found")
    path = profile.primary_audio_path
    if not path or not Path(path).exists():
        raise HTTPException(status_code=404, detail="No reference clip is stored for this voice")
    return FileResponse(path)
