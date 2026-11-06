"""
Voice domain services: reference-clip storage and demo-voice seeding.
"""

from __future__ import annotations

import re
import uuid
from pathlib import Path

import numpy as np

from app.audio.preprocess import AudioPreprocessor
from app.audio.quality import AudioQualityChecker
from app.core.logging_setup import get_logger
from app.data.models import VoiceClip, VoiceProfile
from app.data.voice_repo import voice_repo

logger = get_logger("voice_service")


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug[:40] or "voice"


def store_reference_audio(source: Path, name: str) -> VoiceClip:
    """Preprocesses a reference recording and copies it into the voices directory."""
    try:
        import soundfile as sf

        from app.api.server import paths

        audio, sample_rate = sf.read(str(source), dtype="float32", always_2d=False)
    except Exception as exc:
        raise ValueError(f"Could not read reference audio: {exc}") from exc

    if np is None:
        raise RuntimeError("numpy is required to preprocess reference audio.")
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


def seed_demo_voice() -> None:
    """Creates one reference profile on first launch so Studio is never empty."""
    if voice_repo.list_all_profiles():
        return

    if np is None:
        return

    sample_rate = 24000
    duration = 6.0
    timeline = np.linspace(0, duration, int(sample_rate * duration), endpoint=False)
    tone = (
        0.28 * np.sin(2 * 3.14159265358979 * 165 * timeline)
        + 0.12 * np.sin(2 * 3.14159265358979 * 330 * timeline)
        + 0.06 * np.sin(2 * 3.14159265358979 * 495 * timeline)
    ).astype(np.float32)

    from app.api.server import paths

    destination = paths.voices_dir / "default_narrator.wav"
    try:
        import soundfile as sf

        sf.write(str(destination), tone, sample_rate)
    except Exception as exc:
        logger.warning("Could not write the demo reference clip: %s", exc)
        return

    voice_repo.create_profile(
        VoiceProfile(
            name="Default Narrator",
            language="en",
            notes="Factory demo voice. Replace it with your own reference recording.",
            consent_confirmed=True,
            clips=[
                VoiceClip(
                    file_path=str(destination),
                    original_filename="default_narrator.wav",
                    duration_seconds=duration,
                    sample_rate=sample_rate,
                    is_active=True,
                    quality_score=95,
                )
            ],
        )
    )
    logger.info("Seeded the default demo voice profile.")
