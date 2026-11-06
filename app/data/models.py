"""
Domain data models for voices, audio clips, generation history, and model assets.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


def utc_now_iso() -> str:
    """Returns current UTC ISO timestamp."""
    return datetime.now(timezone.utc).isoformat()


@dataclass
class QualityReport:
    """Report generated from analyzing reference voice audio quality."""

    score: int  # 0 to 100
    duration_seconds: float
    sample_rate: int
    channels: int
    snr_db: float
    clipping_ratio: float
    is_acceptable: bool
    warnings: list[str] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class VoiceClip:
    """Represents a clean reference audio clip associated with a voice profile."""

    id: int | None = None
    profile_id: int | None = None
    file_path: str = ""
    original_filename: str = ""
    duration_seconds: float = 0.0
    sample_rate: int = 24000
    is_active: bool = True
    quality_score: int = 0
    created_at: str = field(default_factory=utc_now_iso)


@dataclass
class VoiceProfile:
    """Represents a speaker voice profile in the Voice Library."""

    id: int | None = None
    name: str = ""
    language: str = "en"
    notes: str = ""
    consent_confirmed: bool = False
    consent_timestamp: str | None = None
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)
    active_clip_id: int | None = None
    clips: list[VoiceClip] = field(default_factory=list)

    @property
    def primary_audio_path(self) -> str | None:
        """Returns the file path of the currently active reference clip."""
        for clip in self.clips:
            if clip.is_active and clip.file_path:
                return clip.file_path
        if self.clips and self.clips[0].file_path:
            return self.clips[0].file_path
        return None


@dataclass
class HistoryEntry:
    """Represents a completed or attempted speech generation."""

    id: int | None = None
    voice_id: int | None = None
    voice_name: str = ""
    engine_name: str = ""
    prompt_text: str = ""
    parameters_json: str = "{}"
    seed: int = -1
    audio_path: str = ""
    duration_seconds: float = 0.0
    sample_rate: int = 24000
    created_at: str = field(default_factory=utc_now_iso)


@dataclass
class ModelFile:
    """A single file that makes up a model, verified by sha256 after download."""

    name: str  # filename, saved as <local_dir>/<name>
    url: str
    size: int
    sha256: str


@dataclass
class ModelMetadata:
    """Information regarding a supported or downloaded TTS engine neural model."""

    id: str  # e.g. "chatterbox-tts", "xtts-v2", "f5-tts"
    name: str
    version: str
    license_name: str
    commercial_allowed: bool
    license_notice: str
    download_url: str
    expected_sha256: str
    total_bytes: int
    local_dir: str
    min_ram_gb: int = 8
    recommended: bool = False
    files: list[ModelFile] = field(default_factory=list)
    is_downloaded: bool = False
    download_progress: float = 0.0


@dataclass
class BatchJob:
    """Individual item in a batch synthesis queue."""

    id: int | None = None
    item_index: int = 0
    text: str = ""
    output_filename: str = ""
    output_path: str = ""
    voice_id: int | None = None
    engine_name: str = ""
    status: str = "pending"  # "pending", "running", "done", "failed"
    error_message: str | None = None
    duration_seconds: float = 0.0
