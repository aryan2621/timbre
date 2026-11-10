from __future__ import annotations

import json
import threading
import time
import uuid
from dataclasses import asdict

from app.core.config import config_manager
from app.core.device import device_manager
from app.core.logging_setup import get_logger
from app.core.paths import paths
from app.data.history_repo import history_repo
from app.data.models import HistoryEntry
from app.engines.base import SoundEngine, SoundParameters
from app.services.synthesis_service import (
    _START_LOCK,
    Job,
    JobManager,
    RenderCancelled,
    _ensure_idle,
    _format_eta,
    compute_peaks,
)

logger = get_logger("sounds")

KIND_LABELS = {"sfx": "Sound effect", "music": "Music"}


class SoundJobManager(JobManager):
    def create(
        self, engine: SoundEngine, prompt: str, kind: str, params: SoundParameters
    ) -> Job:
        job = Job(id=uuid.uuid4().hex, seed=params.seed, total_chunks=params.steps)
        with _START_LOCK:
            _ensure_idle()
            with self._lock:
                self._jobs[job.id] = job
                self._prune_locked()
        threading.Thread(
            target=self._run,
            args=(job, engine, prompt, kind, params),
            name=f"sound-{job.id[:8]}",
            daemon=True,
        ).start()
        return job

    def _run(
        self, job: Job, engine: SoundEngine, prompt: str, kind: str, params: SoundParameters
    ) -> None:
        started = time.time()
        failed = False
        try:
            job.state = "running"
            job.message = f"Preparing {engine.name}"
            with engine.lock:
                if not engine.is_loaded() and not engine.load_model():
                    raise RuntimeError(f"Could not load {engine.name}.")
                if job.cancel_event.is_set():
                    raise RenderCancelled()
                job.message = "Generating"
                audio, sample_rate = engine.generate(
                    prompt, params, on_step=lambda step, total: self._on_step(job, started, step, total)
                )

            import soundfile as sf

            output_path = paths.history_dir / f"sound_{int(time.time() * 1000)}.wav"
            output_path.parent.mkdir(parents=True, exist_ok=True)
            sf.write(str(output_path), audio, sample_rate)

            duration = float(len(audio) / sample_rate)
            entry = history_repo.add_entry(
                HistoryEntry(
                    voice_name=KIND_LABELS.get(kind, "Sound"),
                    engine_name=engine.name,
                    prompt_text=prompt,
                    parameters_json=json.dumps(asdict(params)),
                    seed=params.seed,
                    audio_path=str(output_path),
                    duration_seconds=duration,
                    sample_rate=int(sample_rate),
                    kind=kind,
                )
            )
            job.audio_path = str(output_path)
            job.audio_url = f"/api/history/{entry.id}/audio"
            job.peaks = compute_peaks(audio)
            job.duration_seconds = round(duration, 3)
            job.sample_rate = int(sample_rate)
            job.state = "done"
            job.progress = 100.0
            job.eta = "0s"
            job.message = f"Generated in {time.time() - started:.1f}s"
        except RenderCancelled:
            job.state = "cancelled"
            job.message = "Cancelled"
        except Exception as exc:  # noqa: BLE001 - surfaced to the UI as job.error
            logger.exception("Sound job %s failed", job.id)
            message = str(exc)
            if "out of memory" in message.lower():
                message = device_manager.format_oom_message(exc)
            job.state = "failed"
            job.error = message
            job.message = "Generation failed"
            failed = True
        finally:
            if failed or config_manager.config.clear_device_cache_after_job:
                device_manager.clear_cache()

    @staticmethod
    def _on_step(job: Job, started: float, step: int, total: int) -> None:
        if job.cancel_event.is_set():
            raise RenderCancelled()
        job.current_chunk = step
        job.total_chunks = total
        job.progress = round(step / max(total, 1) * 100.0, 2)
        job.message = f"Step {step} of {total}"
        if step and total:
            job.eta = _format_eta((time.time() - started) / step * (total - step))


sound_manager = SoundJobManager()
