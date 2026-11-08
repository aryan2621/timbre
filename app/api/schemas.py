"""
Pydantic request models and response serialization helpers for the VoiceClone API.
"""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field

from app.api.downloads import download_manager
from app.core.system_info import SystemSpecs
from app.data.model_catalog import is_model_present, model_local_path
from app.data.model_fit import assess_fit
from app.data.models import HistoryEntry, ModelMetadata, VoiceClip, VoiceProfile
from app.engines.base import SoundEngine, TTSEngine
from app.engines.registry import engine_registry, sound_registry

AUDIO_EXTENSIONS = {".wav", ".flac", ".ogg", ".mp3", ".m4a", ".aac", ".aiff", ".aif"}
MAX_PEAKS = 240


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class SynthesisParamsIn(BaseModel):
    temperature: float = Field(0.75, ge=0.0, le=5.0)
    cfg_weight: float = Field(2.5, ge=0.0, le=20.0)
    exaggeration: float = Field(1.0, ge=0.0, le=5.0)
    speed: float = Field(1.0, ge=0.25, le=4.0)
    seed: int = -1
    language: str = "en"
    enable_watermark: bool = True
    top_p: float = Field(0.85, gt=0.0, le=1.0)
    repetition_penalty: float = Field(1.8, ge=1.0, le=10.0)
    extra: dict[str, float | int | str | bool] = Field(default_factory=dict)


class SynthesisRequest(BaseModel):
    voice_id: int
    engine_name: str
    text: str
    params: SynthesisParamsIn = Field(default_factory=SynthesisParamsIn)
    sentence_pause_ms: int = Field(250, ge=0, le=5000)


class SoundParamsIn(BaseModel):
    duration_seconds: float = Field(10.0, ge=1.0, le=600.0)
    steps: int = Field(100, ge=1, le=500)
    guidance: float = Field(7.0, ge=0.0, le=30.0)
    seed: int = -1
    negative_prompt: str = Field("", max_length=500)
    lyrics: str = Field("", max_length=4000)
    extra: dict[str, float | int | str | bool] = Field(default_factory=dict)


class SoundRequest(BaseModel):
    engine_name: str
    prompt: str = Field(max_length=1000)
    kind: Literal["sfx", "music"] = "sfx"
    params: SoundParamsIn = Field(default_factory=SoundParamsIn)


class VoiceCreateRequest(BaseModel):
    name: str
    language: str = "en"
    notes: str = ""
    reference_path: str = ""
    consent_confirmed: bool = False


class BatchItemIn(BaseModel):
    text: str
    filename: str = ""


class BatchRequest(BaseModel):
    voice_id: int
    engine_name: str
    items: list[BatchItemIn]
    params: SynthesisParamsIn = Field(default_factory=SynthesisParamsIn)
    sentence_pause_ms: int = Field(250, ge=0, le=5000)
    output_dir: str | None = None


# ---------------------------------------------------------------------------
# Serialization helpers
# ---------------------------------------------------------------------------


def clip_to_dict(clip: VoiceClip) -> dict[str, Any]:
    return {
        "id": clip.id,
        "profile_id": clip.profile_id,
        "file_path": clip.file_path,
        "original_filename": clip.original_filename,
        "duration_seconds": clip.duration_seconds,
        "sample_rate": clip.sample_rate,
        "is_active": clip.is_active,
        "quality_score": clip.quality_score,
        "created_at": clip.created_at,
    }


def profile_to_dict(profile: VoiceProfile) -> dict[str, Any]:
    return {
        "id": profile.id,
        "name": profile.name,
        "language": profile.language,
        "notes": profile.notes,
        "consent_confirmed": profile.consent_confirmed,
        "consent_timestamp": profile.consent_timestamp,
        "created_at": profile.created_at,
        "updated_at": profile.updated_at,
        "clips": [clip_to_dict(clip) for clip in profile.clips],
        "primary_audio_path": profile.primary_audio_path,
    }


def history_to_dict(entry: HistoryEntry) -> dict[str, Any]:
    return {
        "id": entry.id,
        "voice_id": entry.voice_id,
        "voice_name": entry.voice_name,
        "engine_name": entry.engine_name,
        "prompt_text": entry.prompt_text,
        "parameters_json": entry.parameters_json,
        "seed": entry.seed,
        "audio_path": entry.audio_path,
        "duration_seconds": entry.duration_seconds,
        "sample_rate": entry.sample_rate,
        "created_at": entry.created_at,
        "kind": entry.kind,
    }


def _controls(engine: Any) -> list[dict[str, Any]]:
    return [asdict(spec) for spec in engine.controls]


def engine_to_dict(engine: TTSEngine) -> dict[str, Any]:
    license_info = engine.license_info
    reason = engine.unavailable_reason()
    return {
        "name": engine.name,
        "license_name": license_info.name,
        "license_url": license_info.url,
        "commercial_permitted": license_info.commercial_permitted,
        "license_notice": license_info.notice,
        "supported_languages": list(engine.supported_languages),
        "model_id": engine.model_id,
        "controls": _controls(engine),
        "native_sample_rate": engine.native_sample_rate,
        "requires_gpu_recommended": engine.requires_gpu_recommended,
        "is_available": reason is None,
        "unavailable_reason": reason,
        "is_loaded": engine.is_loaded(),
        "default_params": asdict(engine.get_default_params()),
    }


def sound_engine_to_dict(engine: SoundEngine) -> dict[str, Any]:
    license_info = engine.license_info
    return {
        "name": engine.name,
        "license_name": license_info.name,
        "license_url": license_info.url,
        "commercial_permitted": license_info.commercial_permitted,
        "license_notice": license_info.notice,
        "native_sample_rate": engine.native_sample_rate,
        "max_duration_seconds": engine.max_duration_seconds,
        "kinds": list(engine.kinds),
        "supports_lyrics": engine.supports_lyrics,
        "supports_negative_prompt": engine.supports_negative_prompt,
        "requires_gpu_recommended": engine.requires_gpu_recommended,
        "is_available": engine.is_available(),
        "unavailable_reason": engine.unavailable_reason(),
        "model_id": engine.model_id,
        "controls": _controls(engine),
        "is_loaded": engine.is_loaded(),
        "default_params": asdict(engine.get_default_params()),
    }


def model_to_dict(model: ModelMetadata, models_dir: Path, specs: SystemSpecs) -> dict[str, Any]:
    installed = is_model_present(model, models_dir)
    return {
        "id": model.id,
        "name": model.name,
        "version": model.version,
        "license_name": model.license_name,
        "commercial_allowed": model.commercial_allowed,
        "license_notice": model.license_notice,
        "total_bytes": model.total_bytes,
        "is_downloaded": installed,
        "category": model.category,
        "requires_token": bool(model.gated_url),
        "gated_url": model.gated_url,
        "min_memory_gb": model.min_memory_gb,
        "fit": assess_fit(model, specs, installed).to_dict(),
        "unavailable_reason": next(
            (
                e.unavailable_reason()
                for e in (*engine_registry.get_all_engines(), *sound_registry.get_all_engines())
                if e.model_id == model.id
            ),
            None,
        ),
        "local_path": str(model_local_path(model, models_dir)),
        "download_job": (
            job.to_dict() if (job := download_manager.active_for_model(model.id)) else None
        ),
    }
