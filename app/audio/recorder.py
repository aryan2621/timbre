"""
Microphone audio recorder with real-time VU meter callback and phonetically balanced scripts.
"""

from __future__ import annotations

import math
from pathlib import Path
import threading
import time
from typing import List, Optional

try:
    import numpy as np
except ImportError:
    np = None

from app.core.logging_setup import get_logger
from app.core.paths import paths

logger = get_logger("recorder")

# Phonetically balanced sentences (Harvard sentences & pangrams)
PHONETIC_SCRIPTS = [
    "The birch canoe slid on the smooth planks, while glue the sheet to the dark blue background.",
    "A quick movement of the enemy will jeopardize six gunboats, so open the crate but don't drop the glass.",
    "The soft cushion is very warm and cozy, and the juice of lemons makes fine punch.",
    "Four hours of steady work brought us up into the mountain pass above the clouds.",
    "Pack my box with five dozen liquor jugs, and watch the bright red sun rise over the ocean.",
]


class AudioRecorder:
    """Records microphone audio using sounddevice with live level monitoring."""

    def __init__(self, sample_rate: int = 24000) -> None:
        self.sample_rate = sample_rate
        self.is_recording = False
        self._stream = None
        self._frames: List[np.ndarray] = []
        self._lock = threading.Lock()
        self.last_dbfs: float = -100.0  # read by the GUI thread; written by the audio callback
        self._start_time: float = 0.0

    @staticmethod
    def get_suggested_script(index: int = 0) -> str:
        """Returns a phonetically balanced reference script for voice calibration."""
        return PHONETIC_SCRIPTS[index % len(PHONETIC_SCRIPTS)]

    @staticmethod
    def list_input_devices() -> List[dict]:
        """Queries sounddevice for available audio capture devices."""
        devices = []
        try:
            import sounddevice as sd  # type: ignore
            all_devices = sd.query_devices()
            for idx, dev in enumerate(all_devices):
                if dev.get("max_input_channels", 0) > 0:
                    devices.append({
                        "id": idx,
                        "name": dev.get("name", f"Device {idx}"),
                        "channels": dev.get("max_input_channels", 1),
                        "default_sr": int(dev.get("default_samplerate", 44100)),
                    })
        except Exception as e:
            logger.warning("Failed to query audio input devices: %s", e)
        return devices

    def start_recording(self, device_id: Optional[int] = None) -> bool:
        """Begins streaming microphone input into audio frames."""
        if self.is_recording:
            logger.warning("Recording already in progress.")
            return False

        try:
            import sounddevice as sd  # type: ignore
        except ImportError:
            logger.error("sounddevice package is not installed. Microphone recording unavailable.")
            return False

        with self._lock:
            self._frames = []

        def audio_callback(indata, frames, time_info, status):
            if status:
                logger.debug("Audio input status: %s", status)
            with self._lock:
                if self.is_recording:
                    self._frames.append(indata.copy())

            # Calculate dBFS for VU meter
            mono = indata[:, 0] if indata.ndim > 1 else indata
            rms = np.sqrt(np.mean(mono**2) + 1e-12)
            dbfs = 20.0 * math.log10(max(rms, 1e-5))  # Clamped to -100 dBFS floor
            self.last_dbfs = dbfs

        try:
            self._stream = sd.InputStream(
                samplerate=self.sample_rate,
                channels=1,
                dtype="float32",
                device=device_id,
                callback=audio_callback,
                blocksize=1024,
            )
            self._stream.start()
            self.is_recording = True
            self._start_time = time.time()
            logger.info("Microphone recording started (SR: %d).", self.sample_rate)
            return True
        except Exception as e:
            logger.error("Failed to open audio input stream: %s", e)
            self.is_recording = False
            if self._stream is not None:
                try:
                    self._stream.close()
                except Exception:
                    pass
                self._stream = None
            return False

    def stop_recording(self) -> Optional[np.ndarray]:
        """Stops the recording stream and returns concatenated numpy audio array."""
        if not self.is_recording:
            return None

        self.is_recording = False
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception as e:
                logger.warning("Error stopping recording stream: %s", e)
            self._stream = None

        with self._lock:
            if not self._frames:
                logger.warning("No audio frames recorded.")
                return None
            full_audio = np.concatenate(self._frames, axis=0).flatten()
            self._frames.clear()

        duration = len(full_audio) / self.sample_rate
        logger.info("Recording finished. Captured %.2f seconds.", duration)
        return full_audio

    def save_recorded_audio(self, audio: np.ndarray, file_path: Path) -> bool:
        """Saves recorded numpy audio data to a WAV file."""
        try:
            import soundfile as sf  # type: ignore
            file_path.parent.mkdir(parents=True, exist_ok=True)
            sf.write(str(file_path), audio, self.sample_rate, subtype="PCM_16")
            logger.info("Saved recorded audio to %s", file_path)
            return True
        except Exception as e:
            logger.error("Failed to save audio to %s: %s", file_path, e)
            return False
