"""
Background download worker with HTTP Range resumption, SHA-256 verification,
and download speed calculation.
"""

from __future__ import annotations

import hashlib
import time
import urllib.error
import urllib.request
from pathlib import Path

try:
    from PySide6.QtCore import QObject, QThread, Signal  # type: ignore
except ImportError:
    class Signal:
        def __init__(self, *args):
            pass

        def emit(self, *args):
            pass
    class QObject:
        pass

    class QThread:
        def start(self):
            pass

        def wait(self):
            pass

from app.core.logging_setup import get_logger

logger = get_logger("download_worker")


class ModelDownloadWorker(QThread):
    """Downloads model checkpoint files in a background thread."""

    progress_updated = Signal(str, float, float, str)  # (model_id, percent, speed_mb_s, status_text)
    download_finished = Signal(str, str)               # (model_id, local_file_path)
    download_failed = Signal(str, str)                 # (model_id, error_message)

    def __init__(
        self,
        model_id: str,
        download_url: str,
        destination_path: Path,
        expected_sha256: str | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.model_id = model_id
        self.download_url = download_url
        self.destination_path = destination_path
        self.expected_sha256 = expected_sha256
        self._is_cancelled = False

    def cancel(self) -> None:
        """Flags download for cancellation."""
        self._is_cancelled = True

    def run(self) -> None:
        self._is_cancelled = False
        dest = self.destination_path
        dest.parent.mkdir(parents=True, exist_ok=True)
        part_file = dest.with_suffix(dest.suffix + ".part")

        existing_bytes = part_file.stat().st_size if part_file.exists() else 0
        headers = {}
        if existing_bytes > 0:
            headers["Range"] = f"bytes={existing_bytes}-"
            logger.info("Resuming download from byte %d for %s", existing_bytes, self.model_id)

        try:
            req = urllib.request.Request(self.download_url, headers=headers)
            try:
                response_cm = urllib.request.urlopen(req, timeout=30)
            except urllib.error.HTTPError as http_err:
                if http_err.code != 416 or existing_bytes == 0:
                    raise
                response_cm = None  # .part already holds the whole file
            if response_cm is None:
                self._finalize(part_file, dest)
                return
            with response_cm as response:
                if existing_bytes > 0 and response.status != 206:
                    existing_bytes = 0  # server ignored Range and is sending the full body
                total_size = response.headers.get("Content-Length")
                total_bytes = int(total_size) + existing_bytes if total_size else 0

                mode = "ab" if existing_bytes > 0 else "wb"
                downloaded_bytes = existing_bytes
                last_time = time.time()
                bytes_since_last = 0
                speed_mb_s = 0.0

                with open(part_file, mode) as f:
                    while True:
                        if self._is_cancelled:
                            logger.info("Download cancelled for %s", self.model_id)
                            self.download_failed.emit(self.model_id, "Download cancelled by user.")
                            return

                        chunk = response.read(64 * 1024)  # 64 KB chunks
                        if not chunk:
                            break

                        f.write(chunk)
                        downloaded_bytes += len(chunk)
                        bytes_since_last += len(chunk)

                        now = time.time()
                        dt = now - last_time
                        if dt >= 0.5:
                            speed_mb_s = (bytes_since_last / (1024 * 1024)) / dt
                            percent = (downloaded_bytes / total_bytes * 100.0) if total_bytes > 0 else 0.0
                            dl_mb = downloaded_bytes / (1024 * 1024)
                            tot_mb = total_bytes / (1024 * 1024) if total_bytes > 0 else 0.0
                            status_str = f"{dl_mb:.1f} MB / {tot_mb:.1f} MB ({speed_mb_s:.2f} MB/s)"

                            self.progress_updated.emit(self.model_id, percent, speed_mb_s, status_str)
                            last_time = now
                            bytes_since_last = 0

            self._finalize(part_file, dest)

        except Exception as e:
            logger.error("Download failed for %s: %s", self.model_id, e)
            self.download_failed.emit(self.model_id, f"Download failed: {str(e)}")

    def _finalize(self, part_file: Path, dest: Path) -> None:
        """Atomic rename from .part to destination, then optional checksum verification."""
        if part_file.exists():
            if dest.exists():
                dest.unlink()
            part_file.rename(dest)

        if self.expected_sha256 and self.expected_sha256.strip():
            self.progress_updated.emit(self.model_id, 99.0, 0.0, "Verifying SHA-256 integrity")
            if not self._verify_sha256(dest, self.expected_sha256):
                dest.unlink(missing_ok=True)
                self.download_failed.emit(self.model_id, "SHA-256 checksum mismatch! Download corrupted.")
                return

        logger.info("Successfully downloaded and verified %s -> %s", self.model_id, dest)
        self.download_finished.emit(self.model_id, str(dest))

    @staticmethod
    def _verify_sha256(file_path: Path, expected_hash: str) -> bool:
        """Computes SHA-256 of file in blocks and verifies against expected hash."""
        sha = hashlib.sha256()
        with open(file_path, "rb") as f:
            while chunk := f.read(128 * 1024):
                sha.update(chunk)
        calculated = sha.hexdigest().lower()
        return calculated == expected_hash.strip().lower()

