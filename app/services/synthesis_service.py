"""
Background synthesis orchestration services for the VoiceClone API.

Owns the render pipeline (chunking, stitching, crossfades), the synchronous
job managers and waveform peak extraction used by the transport layer.
"""

from __future__ import annotations

import io
import json
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from app.audio.chunker import TextChunker
from app.audio.stitch import prepare_chunk, stitch_chunks
from app.core.config import config_manager
from app.core.device import device_manager
from app.core.logging_setup import get_logger
from app.core.paths import paths
from app.data.history_repo import history_repo
from app.data.models import HistoryEntry
from app.engines.base import SynthesisParameters, TTSEngine

logger = get_logger("synthesis")

MAX_PEAKS = 240
_PEAKS_CACHE: dict[str, tuple[float, int, list[float]]] = {}
_PEAKS_CACHE_LIMIT = 128


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def compute_peaks(audio: Any, count: int = MAX_PEAKS) -> list[float]:
    """Downsamples a waveform into normalized max-amplitude columns for the UI."""
    if audio is None or len(audio) < 1024:
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


def _format_eta(seconds: float) -> str:
    if seconds <= 0:
        return "0s"
    if seconds < 60:
        return f"{int(seconds)}s"
    return f"{int(seconds // 60)}m {int(seconds % 60)}s"


def _wav_bytes(audio: Any, sample_rate: int) -> bytes:
    import soundfile as sf

    buffer = io.BytesIO()
    sf.write(buffer, audio, sample_rate, format="WAV", subtype="PCM_16")
    return buffer.getvalue()


class RenderCancelled(Exception):
    """Raised inside a render loop when the job was cancelled."""


class RenderBusy(Exception):
    """Raised when a render or batch is already queued or running."""


_ACTIVE_STATES = {"queued", "running"}
_START_LOCK = threading.Lock()


def _ensure_idle() -> None:
    """One GPU, one render: refuse to start while any job is still active."""
    from app.services.sound_service import sound_manager

    for manager in (job_manager, batch_manager, sound_manager):
        if any(job.state in _ACTIVE_STATES for job in list(manager._jobs.values())):
            raise RenderBusy("Another render is already running. Wait for it or cancel it first.")


def unique_path(directory: Path, filename: str) -> Path:
    """Returns directory/filename, or name_2.ext, name_3.ext... if taken."""
    candidate = directory / filename
    stem, suffix = Path(filename).stem, Path(filename).suffix
    counter = 2
    while candidate.exists():
        candidate = directory / f"{stem}_{counter}{suffix}"
        counter += 1
    return candidate


def _render_chunks(
    engine: TTSEngine,
    profile: Any,
    text: str,
    params: SynthesisParameters,
    sentence_pause_ms: int,
    cancel_event: Any,
    on_message=None,
    on_chunk_start=None,
    on_chunk_done=None,
    on_chunk_audio=None,
) -> tuple[Any, int]:
    """Renders text into one stitched waveform.

    Shared by the single-render job and the batch queue so both produce the
    exact same audio (same chunking, crossfades and sentence pauses).

    The model only generates under ``engine.lock``. CPU work on each finished
    chunk (``engine.postprocess_chunk``, e.g. time-stretch) runs on one worker
    thread, so it overlaps the next chunk's generation. ``on_chunk_done`` and
    ``on_chunk_audio(index, prepared_chunk, sample_rate)`` fire from that
    thread, in chunk order, as soon as each chunk is final: the prepared
    chunks concatenate into exactly the stitched result.
    """
    chunks = TextChunker.chunk_text(
        text, max_chars_per_chunk=config_manager.config.max_chars_per_chunk
    )
    if not chunks:
        raise ValueError("Input text is empty or invalid.")

    reference_path = profile.primary_audio_path or ""
    rendered: list[Any] = []
    sample_rate = engine.native_sample_rate
    chunk_times: list[float] = []
    total = len(chunks)

    def finish(index: int, raw: Any, rate: int) -> Any:
        audio = np.asarray(engine.postprocess_chunk(raw, rate, params), dtype=np.float32)
        if on_chunk_done is not None:
            on_chunk_done(index, total, sum(chunk_times) / len(chunk_times))
        if on_chunk_audio is not None and len(audio):
            on_chunk_audio(
                index,
                prepare_chunk(
                    audio,
                    is_first=not any(len(done) for done in rendered_so_far),
                    sample_rate=rate,
                    pause_ms=sentence_pause_ms,
                ),
                rate,
            )
        rendered_so_far.append(audio)
        return audio

    rendered_so_far: list[Any] = []  # only touched by the single worker thread
    futures = []
    with ThreadPoolExecutor(max_workers=1, thread_name_prefix="postprocess") as pool:
        try:
            for index, chunk_text in enumerate(chunks):
                if cancel_event.is_set():
                    raise RenderCancelled()
                if on_chunk_start is not None:
                    on_chunk_start(index, total)
                chunk_start = time.time()
                with engine.lock:
                    raw, sample_rate = engine.synthesize_chunk(
                        text=chunk_text,
                        reference_audio_path=reference_path,
                        params=params,
                    )
                chunk_times.append(time.time() - chunk_start)
                futures.append(pool.submit(finish, index, raw, sample_rate))
        except BaseException:
            for future in futures:
                future.cancel()
            raise
        rendered = [future.result() for future in futures]

    if cancel_event.is_set():
        raise RenderCancelled()

    if on_message is not None:
        on_message("Stitching audio chunks with crossfades")
    stitched = stitch_chunks(rendered, sample_rate=sample_rate, pause_ms=sentence_pause_ms)
    return stitched, sample_rate


# ---------------------------------------------------------------------------
# Job manager (single render)
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
    error: str | None = None
    audio_url: str | None = None
    audio_path: str | None = None
    peaks: list[float] | None = None
    duration_seconds: float = 0.0
    sample_rate: int = 24000
    seed: int = -1
    created_at: float = field(default_factory=time.time)
    cancel_event: threading.Event = field(default_factory=threading.Event, repr=False)
    # WAV bytes of each finished chunk, for play-while-rendering.
    live_chunks: list[bytes] = field(default_factory=list, repr=False)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "chunks_ready": len(self.live_chunks),
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


class JobManager:
    """Runs synthesis on a background thread and exposes pollable status."""

    def __init__(self, max_jobs: int = 100) -> None:
        self._jobs: dict[str, Job] = {}
        self._lock = threading.Lock()
        self._max_jobs = max_jobs

    def create(
        self,
        engine: TTSEngine,
        profile: Any,
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
        with _START_LOCK:
            _ensure_idle()
            with self._lock:
                for old in self._jobs.values():
                    old.live_chunks = []  # the finished file replaces them
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

    def get(self, job_id: str) -> Job | None:
        with self._lock:
            return self._jobs.get(job_id)

    def cancel(self, job_id: str) -> Job | None:
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
            job for job in self._jobs.values() if job.state in {"done", "failed", "cancelled"}
        ]
        finished.sort(key=lambda item: item.created_at)
        for job in finished[: max(0, len(self._jobs) - self._max_jobs)]:
            self._jobs.pop(job.id, None)

    def _run(
        self,
        job: Job,
        engine: TTSEngine,
        profile: Any,
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
                    on_chunk_audio=lambda _i, audio, rate: job.live_chunks.append(
                        _wav_bytes(audio, rate)
                    ),
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
    audio_url: str | None = None
    audio_path: str | None = None
    history_id: int | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
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
    items: list[BatchItemState]
    state: str = "queued"
    progress: float = 0.0
    message: str = "Queued"
    error: str | None = None
    eta: str = ""
    output_dir: str | None = None
    completed: int = 0
    failed: int = 0
    current_index: int = 0
    created_at: float = field(default_factory=time.time)
    cancel_event: threading.Event = field(default_factory=threading.Event, repr=False)

    @property
    def total(self) -> int:
        return len(self.items)

    def to_dict(self) -> dict[str, Any]:
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
        self._jobs: dict[str, BatchJob] = {}
        self._lock = threading.Lock()
        self._max_jobs = max_jobs

    def create(
        self,
        engine: TTSEngine,
        profile: Any,
        items: list[BatchItemState],
        params: SynthesisParameters,
        sentence_pause_ms: int,
        output_dir: str | None = None,
    ) -> BatchJob:
        job = BatchJob(id=uuid.uuid4().hex, items=items, output_dir=output_dir)
        job.message = "Queued"
        with _START_LOCK:
            _ensure_idle()
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

    def get(self, job_id: str) -> BatchJob | None:
        with self._lock:
            return self._jobs.get(job_id)

    def cancel(self, job_id: str) -> BatchJob | None:
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

    def _resolve_output_dir(self, output_dir: str | None) -> Any:
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
        profile: Any,
        params: SynthesisParameters,
        sentence_pause_ms: int,
    ) -> None:
        started = time.time()
        directory = self._resolve_output_dir(job.output_dir)
        durations: list[float] = []

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
                line_started = time.time()
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
                    output_path = unique_path(directory, item.filename)
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

                    durations.append(time.time() - line_started)
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
