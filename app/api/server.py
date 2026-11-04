"""
FastAPI sidecar for VoiceClone Studio.

The Tauri/React frontend talks to this service over loopback HTTP. It is a thin
transport layer: all engine, audio, and persistence logic still lives in the
existing ``app`` packages so the PySide6 application keeps working unchanged.
"""

from __future__ import annotations

import json
import os
import random
import re
import shutil
import threading
import time
import uuid
from contextlib import asynccontextmanager
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    import numpy as np
except ImportError:  # pragma: no cover - numpy is a hard requirement in practice
    np = None

from fastapi import Body, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app.audio.preprocess import AudioPreprocessor
from app.audio.quality import AudioQualityChecker
from app.audio.chunker import TextChunker
from app.core.config import AppConfig, config_manager
from app.core.device import device_manager
from app.core.logging_setup import get_logger, setup_logging
from app.core.paths import paths
from app.data.history_repo import history_repo
from app.data.model_catalog import (
    CATALOG_MODELS,
    get_model,
    is_model_present,
    model_local_path,
)
from app.data.models import HistoryEntry, ModelMetadata, VoiceClip, VoiceProfile
from app.data.voice_repo import voice_repo
from app.api.downloads import download_manager
from app.engines.base import SynthesisParameters, TTSEngine
from app.engines.registry import engine_registry
from app.workers.synth_worker import SynthesisWorker

logger = get_logger("api")

API_VERSION = "0.1.0"
DEFAULT_PORT = 8756
AUDIO_EXTENSIONS = {".wav", ".flac", ".ogg", ".mp3", ".m4a", ".aac", ".aiff", ".aif"}
MAX_PEAKS = 240


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class SynthesisParamsIn(BaseModel):
    temperature: float = Field(0.75, ge=0.05, le=3.0)
    cfg_weight: float = Field(2.5, ge=0.0, le=10.0)
    exaggeration: float = Field(1.0, ge=0.0, le=3.0)
    speed: float = Field(1.0, ge=0.25, le=4.0)
    seed: int = -1
    language: str = "en"
    enable_watermark: bool = True
    top_p: float = Field(0.85, gt=0.0, le=1.0)
    repetition_penalty: float = Field(1.8, ge=1.0, le=5.0)


class SynthesisRequest(BaseModel):
    voice_id: int
    engine_name: str
    text: str
    params: SynthesisParamsIn = Field(default_factory=SynthesisParamsIn)
    sentence_pause_ms: int = Field(250, ge=0, le=5000)


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
    items: List[BatchItemIn]
    params: SynthesisParamsIn = Field(default_factory=SynthesisParamsIn)
    sentence_pause_ms: int = Field(250, ge=0, le=5000)
    output_dir: Optional[str] = None


# ---------------------------------------------------------------------------
# Serialization helpers
# ---------------------------------------------------------------------------


def clip_to_dict(clip: VoiceClip) -> Dict[str, Any]:
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


def profile_to_dict(profile: VoiceProfile) -> Dict[str, Any]:
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


def history_to_dict(entry: HistoryEntry) -> Dict[str, Any]:
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
    }


def engine_to_dict(engine: TTSEngine) -> Dict[str, Any]:
    license_info = engine.license_info
    return {
        "name": engine.name,
        "license_name": license_info.name,
        "license_url": license_info.url,
        "commercial_permitted": license_info.commercial_permitted,
        "license_notice": license_info.notice,
        "supported_languages": list(engine.supported_languages),
        "native_sample_rate": engine.native_sample_rate,
        "requires_gpu_recommended": engine.requires_gpu_recommended,
        "is_available": engine.is_available(),
        "is_loaded": engine.is_loaded(),
        "default_params": asdict(engine.get_default_params()),
    }


def model_to_dict(model: ModelMetadata, models_dir: Path) -> Dict[str, Any]:
    return {
        "id": model.id,
        "name": model.name,
        "version": model.version,
        "license_name": model.license_name,
        "commercial_allowed": model.commercial_allowed,
        "license_notice": model.license_notice,
        "total_bytes": model.total_bytes,
        "is_downloaded": is_model_present(model, models_dir),
        "local_path": str(model_local_path(model, models_dir)),
        "download_job": (
            job.to_dict() if (job := download_manager.active_for_model(model.id)) else None
        ),
    }


def compute_peaks(audio: Any, count: int = MAX_PEAKS) -> List[float]:
    """Downsamples a waveform into normalized max-amplitude columns for the UI."""
    if np is None or audio is None:
        return []
    array = np.asarray(audio, dtype=np.float32)
    if array.size == 0:
        return []
    if array.ndim > 1:
        array = array.mean(axis=-1)
    array = np.abs(array)
    total = int(array.size)
    step = max(1, total // count)
    values = [float(array[i : i + step].max()) for i in range(0, total, step)][:count]
    peak = max(values) if values else 0.0
    if peak <= 1e-6:
        return [0.0] * len(values)
    return [round(min(1.0, value / peak), 3) for value in values]


# ---------------------------------------------------------------------------
# Job manager
# ---------------------------------------------------------------------------


@dataclass
class Job:
    id: str
    state: str = "queued"
    progress: float = 0.0
    current_chunk: int = 0
    total_chunks: int = 0
    eta: str = ""
    message: str = "Queued"
    error: Optional[str] = None
    audio_url: Optional[str] = None
    audio_path: Optional[str] = None
    peaks: Optional[List[float]] = None
    duration_seconds: float = 0.0
    sample_rate: int = 24000
    seed: int = -1
    created_at: float = field(default_factory=time.time)
    cancel_event: threading.Event = field(default_factory=threading.Event, repr=False)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "state": self.state,
            "progress": self.progress,
            "current_chunk": self.current_chunk,
            "total_chunks": self.total_chunks,
            "eta": self.eta,
            "message": self.message,
            "error": self.error,
            "audio_url": self.audio_url,
            "peaks": self.peaks,
            "duration_seconds": self.duration_seconds,
            "sample_rate": self.sample_rate,
            "seed": self.seed,
        }


def _format_eta(seconds: float) -> str:
    if seconds <= 0:
        return "0s"
    if seconds < 60:
        return f"{int(seconds)}s"
    return f"{int(seconds // 60)}m {int(seconds % 60)}s"


class RenderCancelled(Exception):
    """Raised inside a render loop when the job was cancelled."""


def _render_chunks(
    engine: TTSEngine,
    profile: VoiceProfile,
    text: str,
    params: SynthesisParameters,
    sentence_pause_ms: int,
    cancel_event: threading.Event,
    on_message=None,
    on_chunk_start=None,
    on_chunk_done=None,
) -> Tuple[Any, int]:
    """Renders text into one stitched waveform.

    Shared by the single-render job and the batch queue so both produce the
    exact same audio (same chunking, crossfades and sentence pauses).
    """
    chunks = TextChunker.chunk_text(
        text, max_chars_per_chunk=config_manager.config.max_chars_per_chunk
    )
    if not chunks:
        raise ValueError("Input text is empty or invalid.")

    reference_path = profile.primary_audio_path or ""
    rendered: List[Any] = []
    sample_rate = engine.native_sample_rate
    chunk_times: List[float] = []

    for index, chunk_text in enumerate(chunks):
        if cancel_event.is_set():
            raise RenderCancelled()
        if on_chunk_start is not None:
            on_chunk_start(index, len(chunks))
        chunk_start = time.time()
        with engine.lock:
            audio, sample_rate = engine.synthesize_chunk(
                text=chunk_text,
                reference_audio_path=reference_path,
                params=params,
            )
        rendered.append(np.asarray(audio, dtype=np.float32) if np is not None else audio)
        chunk_times.append(time.time() - chunk_start)
        if on_chunk_done is not None:
            on_chunk_done(index, len(chunks), sum(chunk_times) / len(chunk_times))

    if cancel_event.is_set():
        raise RenderCancelled()

    if on_message is not None:
        on_message("Stitching audio chunks with crossfades")
    stitched = SynthesisWorker._stitch_chunks_with_crossfade(
        rendered,
        sample_rate=sample_rate,
        pause_ms=sentence_pause_ms,
    )
    return stitched, sample_rate


class JobManager:
    """Runs synthesis on a background thread and exposes pollable status."""

    def __init__(self, max_jobs: int = 100) -> None:
        self._jobs: Dict[str, Job] = {}
        self._lock = threading.Lock()
        self._max_jobs = max_jobs

    def create(
        self,
        engine: TTSEngine,
        profile: VoiceProfile,
        text: str,
        params: SynthesisParameters,
        sentence_pause_ms: int,
    ) -> Job:
        job = Job(id=uuid.uuid4().hex)
        job.seed = params.seed
        job.total_chunks = len(
            TextChunker.chunk_text(
                text, max_chars_per_chunk=config_manager.config.max_chars_per_chunk
            )
        )
        job.message = "Queued"
        with self._lock:
            self._jobs[job.id] = job
            self._prune_locked()

        thread = threading.Thread(
            target=self._run,
            args=(job, engine, profile, text, params, sentence_pause_ms),
            name=f"synth-{job.id[:8]}",
            daemon=True,
        )
        thread.start()
        return job

    def get(self, job_id: str) -> Optional[Job]:
        with self._lock:
            return self._jobs.get(job_id)

    def cancel(self, job_id: str) -> Optional[Job]:
        with self._lock:
            job = self._jobs.get(job_id)
        if job is None:
            return None
        job.cancel_event.set()
        if job.state == "queued":
            job.state = "cancelled"
            job.message = "Cancelled before start"
        else:
            job.message = "Cancelling"
        logger.info("Cancellation requested for job %s", job_id)
        return job

    def _prune_locked(self) -> None:
        if len(self._jobs) <= self._max_jobs:
            return
        finished = [
            job
            for job in self._jobs.values()
            if job.state in {"done", "failed", "cancelled"}
        ]
        finished.sort(key=lambda item: item.created_at)
        for job in finished[: max(0, len(self._jobs) - self._max_jobs)]:
            self._jobs.pop(job.id, None)

    def _run(
        self,
        job: Job,
        engine: TTSEngine,
        profile: VoiceProfile,
        text: str,
        params: SynthesisParameters,
        sentence_pause_ms: int,
    ) -> None:
        started = time.time()
        failed = False
        try:
            job.state = "running"
            job.message = f"Preparing speech model ({engine.name})"

            with engine.lock:
                if not engine.is_loaded() and not engine.load_model():
                    raise RuntimeError(f"Could not load the {engine.name} model.")

            if job.cancel_event.is_set():
                job.state = "cancelled"
                job.message = "Cancelled"
                return

            def on_chunk_start(index: int, total: int) -> None:
                job.message = f"Synthesizing sentence {index + 1} of {total}"
                job.current_chunk = index

            def on_chunk_done(index: int, total: int, average: float) -> None:
                remaining = total - (index + 1)
                job.eta = _format_eta(remaining * average)
                job.current_chunk = index + 1
                job.progress = round(((index + 1) / total) * 100.0, 2)

            try:
                stitched, sample_rate = _render_chunks(
                    engine=engine,
                    profile=profile,
                    text=text,
                    params=params,
                    sentence_pause_ms=sentence_pause_ms,
                    cancel_event=job.cancel_event,
                    on_message=lambda message: setattr(job, "message", message),
                    on_chunk_start=on_chunk_start,
                    on_chunk_done=on_chunk_done,
                )
            except RenderCancelled:
                job.state = "cancelled"
                job.message = "Cancelled"
                return
            job.total_chunks = max(job.total_chunks, 1)

            output_path = paths.history_dir / f"synth_{int(time.time() * 1000)}.wav"
            output_path.parent.mkdir(parents=True, exist_ok=True)
            try:
                import soundfile as sf

                sf.write(str(output_path), stitched, sample_rate)
            except Exception as exc:
                raise RuntimeError(f"Could not write the rendered WAV: {exc}") from exc

            duration = float(len(stitched) / sample_rate) if sample_rate else 0.0
            peaks = compute_peaks(stitched)

            entry = history_repo.add_entry(
                HistoryEntry(
                    voice_id=profile.id,
                    voice_name=profile.name,
                    engine_name=engine.name,
                    prompt_text=text,
                    parameters_json=json.dumps(asdict(params), default=str),
                    seed=params.seed,
                    audio_path=str(output_path),
                    duration_seconds=duration,
                    sample_rate=int(sample_rate),
                )
            )

            job.audio_path = str(output_path)
            job.audio_url = f"/api/history/{entry.id}/audio"
            job.peaks = peaks
            job.duration_seconds = round(duration, 3)
            job.sample_rate = int(sample_rate)
            job.state = "done"
            job.progress = 100.0
            job.eta = "0s"
            job.message = f"Synthesis complete in {time.time() - started:.1f}s"
            logger.info(
                "Job %s finished in %.2fs (%.2fs audio, %d chunks)",
                job.id,
                time.time() - started,
                duration,
                job.total_chunks,
            )
        except Exception as exc:  # noqa: BLE001 - surfaced to the UI as job.error
            logger.exception("Synthesis job %s failed", job.id)
            message = str(exc)
            if "out of memory" in message.lower() or "cuda oom" in message.lower():
                message = device_manager.format_oom_message(exc)
            job.state = "failed"
            job.error = message
            job.message = "Synthesis failed"
            failed = True
        finally:
            # Purging the allocator cache after every job makes the next run
            # re-allocate its blocks, which slows consecutive generations.
            # Only free on failure (OOM) or when explicitly requested.
            if failed or config_manager.config.clear_device_cache_after_job:
                try:
                    device_manager.clear_cache()
                except Exception:  # pragma: no cover - best-effort cleanup
                    logger.debug("Device cache cleanup failed", exc_info=True)


job_manager = JobManager()


# ---------------------------------------------------------------------------
# Batch manager
# ---------------------------------------------------------------------------


@dataclass
class BatchItemState:
    index: int
    filename: str
    text: str
    state: str = "pending"
    duration_seconds: float = 0.0
    audio_url: Optional[str] = None
    audio_path: Optional[str] = None
    history_id: Optional[int] = None
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "index": self.index,
            "filename": self.filename,
            "text": self.text,
            "state": self.state,
            "duration_seconds": self.duration_seconds,
            "audio_url": self.audio_url,
            "history_id": self.history_id,
            "error": self.error,
        }


@dataclass
class BatchJob:
    id: str
    items: List[BatchItemState]
    state: str = "queued"
    progress: float = 0.0
    message: str = "Queued"
    error: Optional[str] = None
    eta: str = ""
    output_dir: Optional[str] = None
    completed: int = 0
    failed: int = 0
    current_index: int = 0
    created_at: float = field(default_factory=time.time)
    cancel_event: threading.Event = field(default_factory=threading.Event, repr=False)

    @property
    def total(self) -> int:
        return len(self.items)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "state": self.state,
            "progress": self.progress,
            "message": self.message,
            "error": self.error,
            "eta": self.eta,
            "total": self.total,
            "completed": self.completed,
            "failed": self.failed,
            "current_index": self.current_index,
            "items": [item.to_dict() for item in self.items],
            "output_dir": self.output_dir,
        }


class BatchManager:
    """Renders a queue of scripts one file at a time on a background thread."""

    def __init__(self, max_jobs: int = 50) -> None:
        self._jobs: Dict[str, BatchJob] = {}
        self._lock = threading.Lock()
        self._max_jobs = max_jobs

    def create(
        self,
        engine: TTSEngine,
        profile: VoiceProfile,
        items: List[BatchItemState],
        params: SynthesisParameters,
        sentence_pause_ms: int,
        output_dir: Optional[str] = None,
    ) -> BatchJob:
        job = BatchJob(id=uuid.uuid4().hex, items=items, output_dir=output_dir)
        job.message = "Queued"
        with self._lock:
            self._jobs[job.id] = job
            self._prune_locked()

        thread = threading.Thread(
            target=self._run,
            args=(job, engine, profile, params, sentence_pause_ms),
            name=f"batch-{job.id[:8]}",
            daemon=True,
        )
        thread.start()
        return job

    def get(self, job_id: str) -> Optional[BatchJob]:
        with self._lock:
            return self._jobs.get(job_id)

    def cancel(self, job_id: str) -> Optional[BatchJob]:
        with self._lock:
            job = self._jobs.get(job_id)
        if job is None:
            return None
        job.cancel_event.set()
        if job.state == "queued":
            job.state = "cancelled"
            job.message = "Cancelled before start"
        else:
            job.message = "Cancelling"
        for item in job.items:
            if item.state == "pending":
                item.state = "cancelled"
        logger.info("Cancellation requested for batch %s", job_id)
        return job

    def _prune_locked(self) -> None:
        if len(self._jobs) <= self._max_jobs:
            return
        finished = [
            job for job in self._jobs.values() if job.state in {"done", "failed", "cancelled"}
        ]
        finished.sort(key=lambda item: item.created_at)
        for job in finished[: max(0, len(self._jobs) - self._max_jobs)]:
            self._jobs.pop(job.id, None)

    def _resolve_output_dir(self, output_dir: Optional[str]) -> Path:
        if output_dir:
            candidate = Path(output_dir).expanduser()
            try:
                candidate.mkdir(parents=True, exist_ok=True)
                return candidate
            except OSError as exc:
                logger.warning("Could not use output folder %s: %s", candidate, exc)
        return paths.history_dir

    def _run(
        self,
        job: BatchJob,
        engine: TTSEngine,
        profile: VoiceProfile,
        params: SynthesisParameters,
        sentence_pause_ms: int,
    ) -> None:
        started = time.time()
        directory = self._resolve_output_dir(job.output_dir)
        durations: List[float] = []

        try:
            job.state = "running"
            job.message = f"Preparing speech model ({engine.name})"
            with engine.lock:
                if not engine.is_loaded() and not engine.load_model():
                    raise RuntimeError(f"Could not load the {engine.name} model.")

            for index, item in enumerate(job.items):
                if job.cancel_event.is_set():
                    job.state = "cancelled"
                    job.message = "Cancelled"
                    break

                job.current_index = index
                job.message = f"Rendering line {index + 1} of {job.total}: {item.filename}"
                item.state = "running"

                try:
                    stitched, sample_rate = _render_chunks(
                        engine=engine,
                        profile=profile,
                        text=item.text,
                        params=params,
                        sentence_pause_ms=sentence_pause_ms,
                        cancel_event=job.cancel_event,
                    )

                    duration = float(len(stitched) / sample_rate) if sample_rate else 0.0
                    output_path = directory / item.filename
                    output_path.parent.mkdir(parents=True, exist_ok=True)
                    try:
                        import soundfile as sf

                        sf.write(str(output_path), stitched, sample_rate)
                    except Exception as exc:  # noqa: BLE001 - reported per item
                        raise RuntimeError(f"Could not write the rendered WAV: {exc}") from exc

                    entry = history_repo.add_entry(
                        HistoryEntry(
                            voice_id=profile.id,
                            voice_name=profile.name,
                            engine_name=engine.name,
                            prompt_text=item.text,
                            parameters_json=json.dumps(asdict(params), default=str),
                            seed=params.seed,
                            audio_path=str(output_path),
                            duration_seconds=duration,
                            sample_rate=int(sample_rate),
                        )
                    )

                    item.state = "done"
                    item.duration_seconds = round(duration, 3)
                    item.audio_path = str(output_path)
                    item.audio_url = f"/api/history/{entry.id}/audio"
                    item.history_id = entry.id
                    job.completed += 1

                    durations.append(time.time() - started)
                    average = sum(durations) / len(durations)
                    remaining = job.total - (index + 1)
                    job.eta = _format_eta(remaining * average)
                except RenderCancelled:
                    item.state = "cancelled"
                    job.state = "cancelled"
                    job.message = "Cancelled"
                    break
                except Exception as exc:  # noqa: BLE001 - one bad line must not stop the queue
                    logger.exception("Batch line %s failed", item.filename)
                    item.state = "failed"
                    item.error = str(exc)
                    job.failed += 1

                job.progress = round(((index + 1) / job.total) * 100.0, 2)

            if job.state != "cancelled":
                job.state = "done"
                job.progress = 100.0
                job.eta = "0s"
                job.message = (
                    f"Rendered {job.completed} of {job.total} lines in "
                    f"{time.time() - started:.1f}s"
                )
            logger.info(
                "Batch %s finished: %d rendered, %d failed",
                job.id,
                job.completed,
                job.failed,
            )
        except Exception as exc:  # noqa: BLE001 - surfaced to the UI as job.error
            logger.exception("Batch job %s failed", job.id)
            job.state = "failed"
            job.error = str(exc)
            job.message = "Batch failed"


batch_manager = BatchManager()


# ---------------------------------------------------------------------------
# Startup helpers
# ---------------------------------------------------------------------------


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
        0.28 * np.sin(2 * np.pi * 165 * timeline)
        + 0.12 * np.sin(2 * np.pi * 330 * timeline)
        + 0.06 * np.sin(2 * np.pi * 495 * timeline)
    ).astype(np.float32)

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


# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(_: FastAPI):
    setup_logging(config_manager.config.log_level)
    logger.info("VoiceClone API %s starting on loopback.", API_VERSION)
    try:
        seed_demo_voice()
    except Exception:  # noqa: BLE001 - never block startup on demo seeding
        logger.exception("Could not seed the demo voice")
    try:
        yield
    finally:
        try:
            engine_registry.unload_all()
        except Exception:  # pragma: no cover
            logger.debug("Engine unload during shutdown failed", exc_info=True)
        logger.info("VoiceClone API stopped.")


app = FastAPI(title="VoiceClone Studio API", version=API_VERSION, lifespan=lifespan)
app.add_middleware(GZipMiddleware, minimum_size=1024)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:1420",
        "http://127.0.0.1:1420",
        "tauri://localhost",
        "http://tauri.localhost",
        "https://tauri.localhost",
        "null",
    ],
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> Dict[str, Any]:
    info = device_manager.get_device_info()
    return {
        "ok": True,
        "version": API_VERSION,
        "device": {
            "type": info.device_type,
            "name": info.device_name,
            "total_memory_mb": info.total_memory_mb,
            "warning": info.warning_message,
        },
        "engines": engine_registry.list_engine_names(),
        "data_dir": str(paths.data_dir),
    }


@app.get("/api/engines")
def list_engines() -> List[Dict[str, Any]]:
    return [engine_to_dict(engine) for engine in engine_registry.get_all_engines()]


@app.get("/api/voices")
def list_voices() -> List[Dict[str, Any]]:
    return [profile_to_dict(profile) for profile in voice_repo.list_all_profiles()]


@app.get("/api/voices/{voice_id}")
def get_voice(voice_id: int) -> Dict[str, Any]:
    profile = voice_repo.get_profile_by_id(voice_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Voice profile not found")
    return profile_to_dict(profile)


@app.post("/api/voices")
def create_voice(payload: VoiceCreateRequest) -> Dict[str, Any]:
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
        if clip.file_path and os.path.exists(clip.file_path):
            try:
                os.remove(clip.file_path)
            except OSError:
                logger.debug("Could not remove orphaned clip %s", clip.file_path)
        raise

    if profile is None:  # pragma: no cover - repository always returns the stored row
        raise HTTPException(status_code=500, detail="Could not store the voice profile")
    return profile_to_dict(profile)


@app.delete("/api/voices/{voice_id}")
def delete_voice(voice_id: int) -> Dict[str, Any]:
    if not voice_repo.delete_profile(voice_id):
        raise HTTPException(status_code=404, detail="Voice profile not found")
    return {"ok": True}


@app.get("/api/voices/{voice_id}/clip")
def voice_clip(voice_id: int) -> FileResponse:
    profile = voice_repo.get_profile_by_id(voice_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Voice profile not found")
    path = profile.primary_audio_path
    if not path or not os.path.exists(path):
        raise HTTPException(status_code=404, detail="No reference clip is stored for this voice")
    return FileResponse(path)


@app.get("/api/history")
def list_history(q: str = "") -> List[Dict[str, Any]]:
    entries = history_repo.search(q, limit=200) if q.strip() else history_repo.list_recent(200)
    return [history_to_dict(entry) for entry in entries]


@app.delete("/api/history/{entry_id}")
def delete_history(entry_id: int) -> Dict[str, Any]:
    if not history_repo.delete_entry(entry_id):
        raise HTTPException(status_code=404, detail="History entry not found")
    return {"ok": True}


@app.delete("/api/history")
def clear_history() -> Dict[str, Any]:
    return {"deleted": history_repo.clear_all()}


@app.get("/api/history/{entry_id}/audio")
def history_audio(entry_id: int) -> FileResponse:
    entry = history_repo.get_entry_by_id(entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="History entry not found")
    if not entry.audio_path or not os.path.exists(entry.audio_path):
        raise HTTPException(status_code=404, detail="Rendered audio file is missing")
    return FileResponse(entry.audio_path)


# Waveform peaks for finished renders, cached by (path, mtime, size).
_PEAKS_CACHE: Dict[str, Tuple[float, int, List[float]]] = {}
_PEAKS_CACHE_LIMIT = 128


@app.get("/api/history/{entry_id}/peaks")
def history_peaks(entry_id: int) -> Dict[str, Any]:
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

    peaks: List[float] = []
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


@app.get("/api/models")
def list_models() -> List[Dict[str, Any]]:
    models_dir = config_manager.get_models_directory()
    return [model_to_dict(model, models_dir) for model in CATALOG_MODELS]


@app.post("/api/models/{model_id}/download")
def start_model_download(model_id: str) -> Dict[str, Any]:
    model = get_model(model_id)
    if model is None:
        raise HTTPException(status_code=404, detail="Unknown model id")
    job = download_manager.start(model, config_manager.get_models_directory())
    return job.to_dict()


@app.delete("/api/models/{model_id}")
def delete_model(model_id: str) -> Dict[str, Any]:
    model = get_model(model_id)
    if model is None:
        raise HTTPException(status_code=404, detail="Unknown model id")
    if download_manager.active_for_model(model_id) is not None:
        raise HTTPException(status_code=409, detail="Cancel the active download first")

    model_path = model_local_path(model, config_manager.get_models_directory())
    if not model_path.exists():
        raise HTTPException(status_code=404, detail="Model weights are not downloaded")
    shutil.rmtree(model_path)
    logger.info("Deleted model weights for %s at %s", model_id, model_path)
    return {"ok": True}


@app.get("/api/downloads/{job_id}")
def get_download(job_id: str) -> Dict[str, Any]:
    job = download_manager.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Download job not found")
    return job.to_dict()


@app.post("/api/downloads/{job_id}/cancel")
def cancel_download(job_id: str) -> Dict[str, Any]:
    job = download_manager.cancel(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Download job not found")
    return job.to_dict()


@app.get("/api/settings")
def get_settings() -> Dict[str, Any]:
    return config_manager.config.to_dict()


@app.put("/api/settings")
def update_settings(payload: Dict[str, Any] = Body(...)) -> Dict[str, Any]:
    valid = AppConfig.__dataclass_fields__.keys()
    filtered = {key: value for key, value in payload.items() if key in valid}
    merged = {**config_manager.config.to_dict(), **filtered}
    next_config = AppConfig.from_dict(merged)
    if not config_manager.save(next_config):
        raise HTTPException(status_code=500, detail="Could not persist settings")
    logger.info("Settings updated via API: %s", ", ".join(sorted(filtered)) or "no changes")
    return config_manager.config.to_dict()


@app.post("/api/synthesize")
def synthesize(payload: SynthesisRequest) -> Dict[str, Any]:
    text = payload.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Text is empty")

    profile = voice_repo.get_profile_by_id(payload.voice_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Voice profile not found")

    engine = engine_registry.get_engine(payload.engine_name)
    if engine is None:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown engine '{payload.engine_name}'. Available: {', '.join(engine_registry.list_engine_names())}",
        )
    if not engine.is_available():
        raise HTTPException(
            status_code=409,
            detail=f"The {engine.name} weights are not downloaded on this machine",
        )

    params = SynthesisParameters(
        temperature=payload.params.temperature,
        cfg_weight=payload.params.cfg_weight,
        exaggeration=payload.params.exaggeration,
        speed=payload.params.speed,
        seed=payload.params.seed,
        top_p=payload.params.top_p,
        repetition_penalty=payload.params.repetition_penalty,
        language=payload.params.language,
        enable_watermark=payload.params.enable_watermark,
    )
    if params.seed < 0:
        params.seed = random.randint(1, 99_999_999)

    job = job_manager.create(
        engine=engine,
        profile=profile,
        text=text,
        params=params,
        sentence_pause_ms=payload.sentence_pause_ms,
    )
    return job.to_dict()


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str) -> Dict[str, Any]:
    job = job_manager.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job.to_dict()


@app.post("/api/jobs/{job_id}/cancel")
def cancel_job(job_id: str) -> Dict[str, Any]:
    job = job_manager.cancel(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return job.to_dict()


@app.get("/api/jobs/{job_id}/audio")
def job_audio(job_id: str) -> FileResponse:
    job = job_manager.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.state != "done" or not job.audio_path or not os.path.exists(job.audio_path):
        raise HTTPException(status_code=404, detail="Job audio is not ready")
    return FileResponse(job.audio_path)


@app.post("/api/batch")
def start_batch(payload: BatchRequest) -> Dict[str, Any]:
    """Queues a whole script file: one rendered file per line."""
    lines = [item for item in payload.items if item.text.strip()]
    if not lines:
        raise HTTPException(status_code=400, detail="The batch queue is empty")

    profile = voice_repo.get_profile_by_id(payload.voice_id)
    if profile is None:
        raise HTTPException(status_code=404, detail="Voice profile not found")

    engine = engine_registry.get_engine(payload.engine_name)
    if engine is None:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Unknown engine '{payload.engine_name}'. "
                f"Available: {', '.join(engine_registry.list_engine_names())}"
            ),
        )
    if not engine.is_available():
        raise HTTPException(
            status_code=409,
            detail=f"The {engine.name} weights are not downloaded on this machine",
        )

    params = SynthesisParameters(
        temperature=payload.params.temperature,
        cfg_weight=payload.params.cfg_weight,
        exaggeration=payload.params.exaggeration,
        speed=payload.params.speed,
        seed=payload.params.seed,
        top_p=payload.params.top_p,
        repetition_penalty=payload.params.repetition_penalty,
        language=payload.params.language,
        enable_watermark=payload.params.enable_watermark,
    )
    if params.seed < 0:
        params.seed = random.randint(1, 99_999_999)

    items = []
    for index, line in enumerate(lines):
        filename = (line.filename or "").strip() or f"line_{index + 1:04d}.wav"
        if not filename.lower().endswith(".wav"):
            filename = f"{Path(filename).stem}.wav"
        items.append(
            BatchItemState(index=index, filename=filename, text=line.text.strip())
        )

    job = batch_manager.create(
        engine=engine,
        profile=profile,
        items=items,
        params=params,
        sentence_pause_ms=payload.sentence_pause_ms,
        output_dir=payload.output_dir,
    )
    return job.to_dict()


@app.get("/api/batch/{job_id}")
def get_batch(job_id: str) -> Dict[str, Any]:
    job = batch_manager.get(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Batch job not found")
    return job.to_dict()


@app.post("/api/batch/{job_id}/cancel")
def cancel_batch(job_id: str) -> Dict[str, Any]:
    job = batch_manager.cancel(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Batch job not found")
    return job.to_dict()


def main() -> None:
    import uvicorn

    setup_logging(config_manager.config.log_level)
    port = int(os.environ.get("VOICECLONE_API_PORT", str(DEFAULT_PORT)))
    logger.info("Starting VoiceClone API on http://127.0.0.1:%d", port)
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")


if __name__ == "__main__":
    main()
