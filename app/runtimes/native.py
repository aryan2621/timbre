from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from collections.abc import Sequence
from pathlib import Path

from app.core.logging_setup import get_logger
from app.core.paths import paths

logger = get_logger("native")

START_TIMEOUT_SECONDS = 180
IDLE_STOP_SECONDS = 180
NATIVE_DIR_ENV = "VOICECLONE_NATIVE_DIR"
DEV_BINARIES = Path(__file__).resolve().parents[2] / "desktop" / "src-tauri" / "binaries"


class NativeUnavailable(RuntimeError):
    pass


def find_native(name: str) -> Path | None:
    exe = f"{name}.exe" if os.name == "nt" else name
    folders = [Path(sys.executable).parent, DEV_BINARIES]
    if os.environ.get(NATIVE_DIR_ENV):
        folders.insert(0, Path(os.environ[NATIVE_DIR_ENV]))
    for folder in folders:
        for candidate in (folder / exe, *sorted(folder.glob(f"{exe}-*"))):
            if candidate.is_file() and candidate.suffix != ".version" and os.access(candidate, os.X_OK):
                return candidate
    return None


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


class NativeServer:
    """One bundled llama.cpp-family server on a free loopback port, started on demand."""

    def __init__(self, binary_name: str, label: str, ready_path: str = "/health") -> None:
        self.binary_name = binary_name
        self.label = label
        self.ready_path = ready_path
        self.lock = threading.RLock()
        self._process: subprocess.Popen | None = None
        self._key: tuple[str, ...] | None = None
        self._port = 0
        self._last_used = time.monotonic()

    def is_available(self) -> bool:
        return find_native(self.binary_name) is not None

    def is_running(self) -> bool:
        return self._alive()

    def _alive(self) -> bool:
        return self._process is not None and self._process.poll() is None

    def ensure(self, args: Sequence[str]) -> str:
        key = tuple(args)
        with self.lock:
            self._last_used = time.monotonic()
            if self._alive() and self._key == key:
                return self.url
            self.stop()
            binary = find_native(self.binary_name)
            if binary is None:
                raise NativeUnavailable(f"The {self.label} engine is not bundled with this build.")
            self._port = _free_port()
            with open(paths.log_dir / f"{self.binary_name}.log", "wb") as log:
                self._process = subprocess.Popen(
                    [str(binary), *args, "--host", "127.0.0.1", "--port", str(self._port)],
                    stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                )
            self._key = key
            self._wait_ready()
            return self.url

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self._port}"

    def _wait_ready(self) -> None:
        deadline = time.monotonic() + START_TIMEOUT_SECONDS
        while time.monotonic() < deadline:
            if not self._alive():
                self._process = None
                raise RuntimeError(f"The {self.label} engine stopped while starting. See {self.binary_name}.log.")
            try:
                with urllib.request.urlopen(self.url + self.ready_path, timeout=2) as response:
                    if response.status == 200:
                        return
            except (urllib.error.URLError, OSError):
                pass
            time.sleep(0.3)
        self.stop()
        raise RuntimeError(f"The {self.label} engine took too long to start.")

    def request(self, path: str, body: dict | None = None, timeout: float = 600) -> dict:
        data = json.dumps(body).encode() if body is not None else None
        request = urllib.request.Request(self.url + path, data=data, headers={"Content-Type": "application/json"})
        return self.send(request, timeout)

    def send(self, request: urllib.request.Request, timeout: float = 600) -> dict:
        return json.loads(self.read(request, timeout) or b"null")

    def read(self, request: urllib.request.Request, timeout: float = 600) -> bytes:
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.read()
        except urllib.error.HTTPError as exc:
            raise RuntimeError(f"{self.label} engine error {exc.code}: {exc.read().decode(errors='replace')[:300]}") from None
        except (urllib.error.URLError, OSError) as exc:
            raise RuntimeError(f"The {self.label} engine failed: {exc}") from None
        finally:
            self._last_used = time.monotonic()

    def stop_if_idle(self) -> None:
        with self.lock:
            if self._alive() and time.monotonic() - self._last_used > IDLE_STOP_SECONDS:
                self.stop()

    def stop(self) -> None:
        with self.lock:
            if self._process is not None:
                self._process.terminate()
                try:
                    self._process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    self._process.kill()
                    self._process.wait()
            self._process = None
            self._key = None
