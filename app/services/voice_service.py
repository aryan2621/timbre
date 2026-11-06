"""
Voice domain services: reference-clip storage.
"""

from __future__ import annotations

import re
import uuid
from pathlib import Path

from app.audio.preprocess import AudioPreprocessor
from app.audio.quality import AudioQualityChecker
from app.core.logging_setup import get_logger
from app.core.paths import paths
from app.data.models import VoiceClip

logger = get_logger("voice_service")


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug[:40] or "voice"


def store_reference_audio(source: Path, name: str) -> VoiceClip:
    """Preprocesses a reference recording and copies it into the voices directory."""
    try:
        import soundfile as sf

        audio, sample_rate = sf.read(str(source), dtype="float32", always_2d=False)
    except Exception as exc:
        raise ValueError(f"Could not read reference audio: {exc}") from exc

    if getattr(audio, "size", 0) == 0:
        raise ValueError("The reference audio file is empty.")

    processed, target_sr = AudioPreprocessor.process_reference_audio(
        audio, int(sample_rate), target_sr=24000
    )
    quality = AudioQualityChecker.analyze(processed, target_sr)

    destination = paths.voices_dir / f"{_slugify(name)}_{uuid.uuid4().hex[:8]}.wav"
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        import soundfile as sf

        sf.write(str(destination), processed, target_sr)
    except Exception as exc:
        raise RuntimeError(f"Could not save the processed reference clip: {exc}") from exc

    return VoiceClip(
        file_path=str(destination),
        original_filename=source.name,
        duration_seconds=round(len(processed) / target_sr, 3),
        sample_rate=int(target_sr),
        is_active=True,
        quality_score=quality.score,
    )
