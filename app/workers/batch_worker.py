"""
Background batch processor for bulk synthesis from .txt, .csv, and .srt files.
"""

from __future__ import annotations

import csv
from pathlib import Path
import re
import time
from typing import List, Optional

try:
    import numpy as np
except ImportError:
    np = None

try:
    from PySide6.QtCore import QObject, QThread, Signal  # type: ignore
except ImportError:
    class Signal:
        def __init__(self, *args): pass
        def emit(self, *args): pass
    class QObject: pass
    class QThread:
        def start(self): pass
        def wait(self): pass

from app.audio.export import AudioExporter
from app.core.logging_setup import get_logger
from app.data.models import BatchJob
from app.engines.base import SynthesisParameters, TTSEngine

logger = get_logger("batch_worker")


class BatchWorker(QThread):
    """Processes a queue of batch synthesis tasks in the background."""

    item_started = Signal(int, str)              # (item_index, filename)
    item_finished = Signal(int, str, float)      # (item_index, output_path, duration_sec)
    item_failed = Signal(int, str)               # (item_index, error_message)
    batch_progress = Signal(int, int, float)     # (completed_count, total_count, percent)
    batch_finished = Signal(int, int)            # (success_count, fail_count)
    batch_error = Signal(str)                    # fatal error that aborted the run

    def __init__(
        self,
        engine: TTSEngine,
        jobs: List[BatchJob],
        reference_audio_path: str | Path,
        params: SynthesisParameters,
        output_directory: Path,
        export_format: str = "wav",
        parent: Optional[QObject] = None,
    ) -> None:
        super().__init__(parent)
        self.engine = engine
        self.jobs = jobs
        self.reference_audio_path = reference_audio_path
        self.params = params
        self.output_directory = output_directory
        self.export_format = export_format
        self._is_cancelled = False
        self._is_paused = False

    def cancel(self) -> None:
        self._is_cancelled = True

    def pause(self) -> None:
        self._is_paused = True

    def resume(self) -> None:
        self._is_paused = False

    def run(self) -> None:
        self._is_cancelled = False
        self._is_paused = False
        self.success_count = 0
        self.fail_count = 0
        try:
            self._process_jobs()
        except Exception as e:
            logger.exception("Batch aborted: %s", e)
            self.batch_error.emit(str(e))
        finally:
            # Always emitted so the UI never stays stuck in the running state.
            self.batch_finished.emit(self.success_count, self.fail_count)

    def _process_jobs(self) -> None:
        with self.engine.lock:
            if not self.engine.is_loaded() and not self.engine.load_model():
                raise RuntimeError(f"Could not load the {self.engine.name} model.")

        total = len(self.jobs)
        self.output_directory.mkdir(parents=True, exist_ok=True)

        for idx, job in enumerate(self.jobs):
            while self._is_paused:
                if self._is_cancelled:
                    break
                time.sleep(0.2)

            if self._is_cancelled:
                logger.info("Batch execution stopped by user.")
                break

            job.status = "running"
            self.item_started.emit(idx, job.output_filename)

            try:
                start_time = time.time()
                with self.engine.lock:
                    audio, sr = self.engine.clone_and_synthesize(
                        text=job.text,
                        reference_audio_path=self.reference_audio_path,
                        params=self.params,
                    )

                # Name comes from user CSV: keep only the basename so it can't escape the folder.
                out_path = self.output_directory / Path(job.output_filename).with_suffix(f".{self.export_format}").name
                success = AudioExporter.export(
                    audio=audio,
                    sample_rate=sr,
                    output_path=out_path,
                    format_str=self.export_format,
                )

                if success:
                    duration = len(audio) / sr
                    job.status = "done"
                    job.duration_seconds = duration
                    job.output_path = str(out_path)
                    self.success_count += 1
                    self.item_finished.emit(idx, str(out_path), duration)
                else:
                    raise RuntimeError("Audio file export failed.")

            except Exception as e:
                logger.error("Batch item %d failed: %s", idx, e)
                job.status = "failed"
                job.error_message = str(e)
                self.fail_count += 1
                self.item_failed.emit(idx, str(e))

            completed = idx + 1
            percent = (completed / total) * 100.0
            self.batch_progress.emit(completed, total, percent)

    @staticmethod
    def parse_file(file_path: Path) -> List[BatchJob]:
        """Parses .txt, .csv, or .srt subtitle files into a list of BatchJob objects."""
        suffix = file_path.suffix.lower()
        jobs: List[BatchJob] = []

        if suffix == ".txt":
            with open(file_path, "r", encoding="utf-8-sig") as f:
                lines = [line.strip() for line in f if line.strip()]
            for i, line in enumerate(lines, 1):
                jobs.append(BatchJob(
                    item_index=i,
                    text=line,
                    output_filename=f"line_{i:04d}.wav",
                ))

        elif suffix == ".csv":
            with open(file_path, "r", encoding="utf-8-sig") as f:
                row_idx = 1
                for n, row in enumerate(csv.reader(f)):
                    if not row:
                        continue
                    if n == 0 and row[0].strip().lower() in ("text", "prompt", "sentence"):
                        continue  # header row
                    text = row[0].strip()
                    custom_name = row[1].strip() if len(row) > 1 and row[1].strip() else f"batch_{row_idx:04d}.wav"
                    if not custom_name.endswith((".wav", ".mp3", ".flac", ".ogg")):
                        custom_name += ".wav"
                    jobs.append(BatchJob(
                        item_index=row_idx,
                        text=text,
                        output_filename=custom_name,
                    ))
                    row_idx += 1

        elif suffix == ".srt":
            with open(file_path, "r", encoding="utf-8-sig") as f:
                content = f.read()
            # Simple SRT regex: block index, timestamp, subtitle text
            blocks = re.split(r"\n\s*\n", content.strip())
            for i, block in enumerate(blocks, 1):
                lines = [l.strip() for l in block.splitlines() if l.strip()]
                # Skip numeric index line and timestamp line
                text_lines = [l for l in lines if not l.isdigit() and "-->" not in l]
                if text_lines:
                    combined_text = " ".join(text_lines)
                    jobs.append(BatchJob(
                        item_index=i,
                        text=combined_text,
                        output_filename=f"subtitle_{i:04d}.wav",
                    ))

        return jobs
