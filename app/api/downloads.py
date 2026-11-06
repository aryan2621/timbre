"""
Background model-download manager for the HTTP sidecar.

Mirrors the behaviour of the Qt ``ModelDownloadWorker`` (Range resume,
``.part`` staging, optional SHA-256 verification) but as a plain thread with a
pollable state object so the React frontend can show progress.
"""

from __future__ import annotations

import hashlib
import threading
import time
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.core.logging_setup import get_logger
from app.data.model_catalog import model_local_path
from app.data.models import ModelMetadata

logger = get_logger("downloads")

CHUNK_BYTES = 64 * 1024
PROGRESS_INTERVAL_SECONDS = 0.4
ACTIVE_STATES = {"queued", "running"}


@dataclass
class DownloadJob:
    id: str
    model_id: str
    model_name: str
    state: str = "queued"
    progress: float = 0.0
    downloaded_bytes: int = 0
    total_bytes: int = 0
    speed_mb_s: float = 0.0
    message: str = "Queued"
    error: str | None = None
    file_path: str | None = None
    created_at: float = field(default_factory=time.time)
    cancel_event: threading.Event = field(default_factory=threading.Event, repr=False)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "model_id": self.model_id,
            "model_name": self.model_name,
            "state": self.state,
            "progress": round(self.progress, 2),
            "downloaded_bytes": self.downloaded_bytes,
            "total_bytes": self.total_bytes,
            "speed_mb_s": round(self.speed_mb_s, 2),
            "message": self.message,
            "error": self.error,
            "file_path": self.file_path,
        }


class DownloadManager:
    """Starts and tracks one download per model."""

    def __init__(self, max_jobs: int = 40) -> None:
        self._jobs: dict[str, DownloadJob] = {}
        self._lock = threading.Lock()
        self._max_jobs = max_jobs

    def start(self, model: ModelMetadata, models_dir: Path) -> DownloadJob:
        with self._lock:
            for job in self._jobs.values():
                if job.model_id == model.id and job.state in ACTIVE_STATES:
                    return job

            job = DownloadJob(id=uuid.uuid4().hex, model_id=model.id, model_name=model.name)
            self._jobs[job.id] = job
            self._prune_locked()

        thread = threading.Thread(
            target=self._run,
            args=(job, model, models_dir),
            name=f"download-{model.id}",
            daemon=True,
        )
        thread.start()
        return job

    def get(self, job_id: str) -> DownloadJob | None:
        with self._lock:
            return self._jobs.get(job_id)

    def active_for_model(self, model_id: str) -> DownloadJob | None:
        with self._lock:
            for job in self._jobs.values():
                if job.model_id == model_id and job.state in ACTIVE_STATES:
                    return job
        return None

    def cancel(self, job_id: str) -> DownloadJob | None:
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
        return job

    def _prune_locked(self) -> None:
        if len(self._jobs) <= self._max_jobs:
            return
        finished = [
            job
            for job in self._jobs.values()
            if job.state not in ACTIVE_STATES
        ]
        finished.sort(key=lambda item: item.created_at)
        for job in finished[: max(0, len(self._jobs) - self._max_jobs)]:
            self._jobs.pop(job.id, None)

    def _run(self, job: DownloadJob, model: ModelMetadata, models_dir: Path) -> None:
        if model.files:
            return self._run_multi(job, model, models_dir)

        destination = model_local_path(model, models_dir) / Path(model.download_url).name
        part_file = destination.with_suffix(destination.suffix + ".part")

        try:
            destination.parent.mkdir(parents=True, exist_ok=True)
            if destination.exists():
                job.state = "done"
                job.progress = 100.0
                job.message = "Already downloaded"
                job.file_path = str(destination)
                return None

            existing_bytes = part_file.stat().st_size if part_file.exists() else 0
            headers = {"Range": f"bytes={existing_bytes}-"} if existing_bytes > 0 else {}

            job.state = "running"
            job.message = "Connecting"
            job.downloaded_bytes = existing_bytes
            job.total_bytes = model.total_bytes if model.total_bytes else 0

            request = urllib.request.Request(model.download_url, headers=headers)
            try:
                response_cm = urllib.request.urlopen(request, timeout=30)
            except urllib.error.HTTPError as http_error:
                if http_error.code != 416 or existing_bytes == 0:
                    raise
                response_cm = None  # The .part file already holds the full body.

            if response_cm is None:
                self._finalize(job, model, part_file, destination)
                return None

            with response_cm as response:
                if existing_bytes > 0 and response.status != 206:
                    existing_bytes = 0  # Server ignored Range and restarted the body.
                content_length = response.headers.get("Content-Length")
                total_bytes = int(content_length) + existing_bytes if content_length else 0
                if total_bytes:
                    job.total_bytes = total_bytes

                downloaded = existing_bytes
                job.downloaded_bytes = downloaded
                mode = "ab" if existing_bytes > 0 else "wb"
                last_time = time.time()
                bytes_since_last = 0

                with open(part_file, mode) as handle:
                    while True:
                        if job.cancel_event.is_set():
                            job.state = "cancelled"
                            job.message = "Download cancelled"
                            logger.info("Download cancelled for %s", model.id)
                            return None

                        chunk = response.read(CHUNK_BYTES)
                        if not chunk:
                            break

                        handle.write(chunk)
                        downloaded += len(chunk)
                        job.downloaded_bytes = downloaded
                        bytes_since_last += len(chunk)

                        now = time.time()
                        elapsed = now - last_time
                        if elapsed >= PROGRESS_INTERVAL_SECONDS:
                            job.speed_mb_s = (bytes_since_last / (1024 * 1024)) / elapsed
                            job.progress = (
                                (downloaded / job.total_bytes) * 100.0 if job.total_bytes else 0.0
                            )
                            downloaded_mb = downloaded / (1024 * 1024)
                            total_mb = job.total_bytes / (1024 * 1024) if job.total_bytes else 0.0
                            job.message = (
                                f"{downloaded_mb:.1f} MB / {total_mb:.1f} MB "
                                f"({job.speed_mb_s:.2f} MB/s)"
                            )
                            last_time = now
                            bytes_since_last = 0

            if job.cancel_event.is_set():
                job.state = "cancelled"
                job.message = "Download cancelled"
                return None

            self._finalize(job, model, part_file, destination)

        except Exception as exc:  # noqa: BLE001 - surfaced to the UI as job.error
            logger.exception("Model download failed for %s", model.id)
            job.state = "failed"
            job.error = f"Download failed: {exc}"
            job.message = "Download failed"

    def _run_multi(self, job: DownloadJob, model: ModelMetadata, models_dir: Path) -> None:
        """Downloads every file in ``model.files`` with Aggregated progress/cancel/SHA-256."""
        try:
            destination_dir = model_local_path(model, models_dir)
            destination_dir.mkdir(parents=True, exist_ok=True)

            total_bytes = sum(f.size for f in model.files)
            job.total_bytes = total_bytes
            job.state = "running"
            job.message = "Connecting"

            downloaded_before_file = 0
            for index, file in enumerate(model.files):
                if job.cancel_event.is_set():
                    job.state = "cancelled"
                    job.message = "Download cancelled"
                    return

                job.message = f"Downloading {file.name} ({index + 1}/{len(model.files)})"
                destination = destination_dir / file.name
                part_file = destination.with_suffix(destination.suffix + ".part")

                if destination.exists():
                    downloaded_before_file += file.size
                    job.downloaded_bytes = downloaded_before_file
                    job.progress = (
                        (downloaded_before_file / total_bytes) * 100.0 if total_bytes else 100.0
                    )
                    continue

                existing_bytes = part_file.stat().st_size if part_file.exists() else 0
                headers = {"Range": f"bytes={existing_bytes}-"} if existing_bytes > 0 else {}

                request = urllib.request.Request(file.url, headers=headers)
                try:
                    response_cm = urllib.request.urlopen(request, timeout=30)
                except urllib.error.HTTPError as http_error:
                    if http_error.code != 416 or existing_bytes == 0:
                        raise
                    response_cm = None  # The .part file already holds the full body.

                if response_cm is None:
                    self._finalize_single(job, file, part_file, destination)
                else:
                    with response_cm as response:
                        if existing_bytes > 0 and response.status != 206:
                            existing_bytes = 0  # Server ignored Range and restarted the body.
                        downloaded_in_file = existing_bytes
                        job.downloaded_bytes = downloaded_before_file + downloaded_in_file
                        mode = "ab" if existing_bytes > 0 else "wb"
                        last_time = time.time()
                        bytes_since_last = 0

                        with open(part_file, mode) as handle:
                            while True:
                                if job.cancel_event.is_set():
                                    job.state = "cancelled"
                                    job.message = "Download cancelled"
                                    logger.info("Download cancelled for %s", model.id)
                                    return

                                chunk = response.read(CHUNK_BYTES)
                                if not chunk:
                                    break

                                handle.write(chunk)
                                downloaded_in_file += len(chunk)
                                job.downloaded_bytes = downloaded_before_file + downloaded_in_file
                                bytes_since_last += len(chunk)

                                now = time.time()
                                elapsed = now - last_time
                                if elapsed >= PROGRESS_INTERVAL_SECONDS:
                                    job.speed_mb_s = (bytes_since_last / (1024 * 1024)) / elapsed
                                    job.progress = (
                                        (job.downloaded_bytes / total_bytes) * 100.0 if total_bytes else 0.0
                                    )
                                    downloaded_mb = job.downloaded_bytes / (1024 * 1024)
                                    total_mb = total_bytes / (1024 * 1024)
                                    job.message = (
                                        f"{downloaded_mb:.1f} MB / {total_mb:.1f} MB "
                                        f"({job.speed_mb_s:.2f} MB/s) — {file.name}"
                                    )
                                    last_time = now
                                    bytes_since_last = 0

                    self._finalize_single(job, file, part_file, destination)

                done_bytes_file = (
                    destination.stat().st_size if destination.exists() else file.size
                )
                downloaded_before_file += max(done_bytes_file, file.size)
                # If _finalize_single failed on checksum, it set job.state; stop here.
                if job.state in {"failed"}:
                    return

            job.state = "done"
            job.progress = 100.0
            job.speed_mb_s = 0.0
            job.file_path = str(destination_dir)
            job.message = "Download complete"
            logger.info("Downloaded model %s (files) to %s", model.id, destination_dir)

        except Exception as exc:  # noqa: BLE001 - surfaced to the UI as job.error
            logger.exception("Model download failed for %s", model.id)
            job.state = "failed"
            job.error = f"Download failed: {exc}"
            job.message = "Download failed"

    def _finalize_single(
        self,
        job: DownloadJob,
        file,
        part_file: Path,
        destination: Path,
    ) -> None:
        if part_file.exists():
            if destination.exists():
                destination.unlink()
            part_file.rename(destination)

        expected = (file.sha256 or "").strip()
        if expected:
            job.message = f"Verifying {file.name}"
            if not self._verify_sha256(destination, expected):
                destination.unlink(missing_ok=True)
                job.state = "failed"
                job.error = f"SHA-256 mismatch for {file.name}. Corrupted download."
                job.message = "Verification failed"
                return

    def _finalize(
        self,
        job: DownloadJob,
        model: ModelMetadata,
        part_file: Path,
        destination: Path,
    ) -> None:
        if part_file.exists():
            if destination.exists():
                destination.unlink()
            part_file.rename(destination)

        expected = (model.expected_sha256 or "").strip()
        if expected:
            job.message = "Verifying SHA-256 integrity"
            job.progress = 99.0
            if not self._verify_sha256(destination, expected):
                destination.unlink(missing_ok=True)
                job.state = "failed"
                job.error = "SHA-256 checksum mismatch. The download was corrupted."
                job.message = "Verification failed"
                return

        job.state = "done"
        job.progress = 100.0
        job.speed_mb_s = 0.0
        job.file_path = str(destination)
        job.message = "Download complete"
        logger.info("Downloaded model %s to %s", model.id, destination)

    @staticmethod
    def _verify_sha256(path: Path, expected_hash: str) -> bool:
        digest = hashlib.sha256()
        with open(path, "rb") as handle:
            while chunk := handle.read(128 * 1024):
                digest.update(chunk)
        return digest.hexdigest().lower() == expected_hash.lower()


download_manager = DownloadManager()
