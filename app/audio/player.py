"""
Thread-safe audio player supporting play, pause, seek, volume, and position callbacks.

Two playback modes are supported:

* **Buffered** – a complete clip is loaded up front and played from memory.
* **Live stream** – chunks are pushed in while the TTS engine is still
  synthesizing, so the first sentence is audible long before the last one is
  rendered. The PortAudio callback drains whatever has arrived so far.
"""

from __future__ import annotations

from enum import Enum
from pathlib import Path
import threading
import time
from typing import List, Optional

try:
    import numpy as np
except ImportError:
    np = None

from app.core.logging_setup import get_logger

logger = get_logger("player")


class PlaybackState(str, Enum):
    STOPPED = "stopped"
    PLAYING = "playing"
    PAUSED = "paused"


class AudioPlayer:
    """Non-blocking audio player with position tracking and volume control."""

    def __init__(self, sample_rate: int = 24000) -> None:
        self.sample_rate = sample_rate
        self.state = PlaybackState.STOPPED
        self.volume: float = 1.0  # 0.0 to 1.0

        self._audio_data: Optional[np.ndarray] = None
        self._current_sample: int = 0
        self._stream = None
        self._lock = threading.RLock()

        # Live streaming state. `_stream_buffer` holds chunks that have not been
        # played yet, `_stream_offset` is the read cursor inside the first
        # buffered chunk, `_stream_played` counts samples already emitted and
        # `_stream_received` counts samples handed over by the producer.
        self._stream_mode: bool = False
        self._stream_buffer: List[np.ndarray] = []
        self._stream_offset: int = 0
        self._stream_played: int = 0
        self._stream_received: int = 0
        self._stream_finished: bool = False

    # ------------------------------------------------------------------
    # Buffered playback
    # ------------------------------------------------------------------

    def load_audio(self, audio: np.ndarray, sample_rate: int) -> None:
        """Loads an in-memory numpy array for playback."""
        self.stop()
        with self._lock:
            self.sample_rate = sample_rate
            self._audio_data = np.asarray(audio, dtype=np.float32).reshape(-1)
            self._current_sample = 0

    def load_file(self, file_path: str | Path) -> bool:
        """Reads audio from disk and loads into the player."""
        try:
            import soundfile as sf  # type: ignore
            data, sr = sf.read(str(file_path), dtype="float32")
            if data.ndim > 1:
                data = np.mean(data, axis=-1)
            self.load_audio(data, sr)
            return True
        except Exception as e:
            logger.error("Failed to load audio file for playback from %s: %s", file_path, e)
            return False

    @property
    def duration_seconds(self) -> float:
        """Returns total duration of loaded audio in seconds."""
        with self._lock:
            if self._stream_mode:
                return self._stream_received / self.sample_rate
            if self._audio_data is None or len(self._audio_data) == 0:
                return 0.0
            return len(self._audio_data) / self.sample_rate

    @property
    def current_position_seconds(self) -> float:
        """Returns current playback position in seconds."""
        with self._lock:
            if self._stream_mode:
                return self._stream_played / self.sample_rate
            return self._current_sample / self.sample_rate

    @property
    def is_streaming(self) -> bool:
        """True while the player is consuming a live chunk stream."""
        return self._stream_mode

    @property
    def has_pending_audio(self) -> bool:
        """True when the live stream still holds audio that has not been played yet."""
        with self._lock:
            return bool(self._stream_buffer) or self._stream_played < self._stream_received

    def play(self) -> bool:
        """Begins or resumes playback."""
        with self._lock:
            if self._stream_mode:
                if self.state == PlaybackState.PLAYING:
                    return True
                if self.state == PlaybackState.PAUSED:
                    self.state = PlaybackState.PLAYING
                    return True
                # The live stream ran to completion: replay the full clip instead.
                if self._audio_data is not None and len(self._audio_data):
                    self._stream_mode = False
                    self._current_sample = 0
                    self.state = PlaybackState.PLAYING
                    return self._start_stream()
                return False

            if self._audio_data is None or len(self._audio_data) == 0:
                logger.warning("No audio loaded to play.")
                return False

            if self.state == PlaybackState.PLAYING:
                return True

            if self.state == PlaybackState.PAUSED:
                self.state = PlaybackState.PLAYING
                return True

        return self._start_stream()

    def pause(self) -> None:
        """Pauses active playback without resetting position."""
        with self._lock:
            if self.state == PlaybackState.PLAYING:
                self.state = PlaybackState.PAUSED

    def resume(self) -> None:
        """Resumes playback if currently paused."""
        if self.state == PlaybackState.PAUSED:
            self.play()

    def stop(self) -> None:
        """Stops playback and resets playhead to start."""
        with self._lock:
            self.state = PlaybackState.STOPPED
            self._current_sample = 0
            self._stream_mode = False
            self._stream_buffer = []
            self._stream_offset = 0
            self._stream_played = 0
            self._stream_received = 0
            self._stream_finished = False

        self._close_stream()

    def _close_stream(self) -> None:
        if self._stream is not None:
            try:
                self._stream.stop()
                self._stream.close()
            except Exception:
                pass
            self._stream = None

    def seek(self, position_seconds: float) -> None:
        """Seeks to the designated timestamp in seconds."""
        with self._lock:
            if self._stream_mode:
                # A live stream is append-only: there is no timeline to seek in.
                return
            if self._audio_data is None:
                return
            target_sample = int(position_seconds * self.sample_rate)
            self._current_sample = max(0, min(len(self._audio_data), target_sample))

    def set_volume(self, volume: float) -> None:
        """Adjusts playback volume multiplier (0.0 to 1.0)."""
        self.volume = max(0.0, min(1.0, volume))

    # ------------------------------------------------------------------
    # Live streaming API
    # ------------------------------------------------------------------

    def start_stream_mode(self, sample_rate: Optional[int] = None) -> bool:
        """
        Opens a live output stream that plays audio as it arrives.

        Chunks pushed with :meth:`append_chunk` are played in order while the
        synthesis engine is still producing the rest of the text.
        """
        if np is None:
            logger.error("numpy is not available; live streaming is disabled.")
            return False

        self.stop()
        with self._lock:
            if sample_rate:
                self.sample_rate = sample_rate
            self._stream_mode = True
            self._stream_buffer = []
            self._stream_offset = 0
            self._stream_played = 0
            self._stream_received = 0
            self._stream_finished = False
            self.state = PlaybackState.PLAYING

        if not self._open_output_stream(self._playback_callback):
            with self._lock:
                self._stream_mode = False
                self.state = PlaybackState.STOPPED
            return False
        return True

    def append_chunk(self, audio: np.ndarray, sample_rate: int) -> int:
        """
        Appends a rendered chunk to the live stream buffer.

        Safe to call from any thread (e.g. a Qt worker slot); the PortAudio
        callback drains the buffer on the audio thread.
        """
        if np is None or audio is None:
            return 0
        data = np.asarray(audio, dtype=np.float32).reshape(-1)
        if data.size == 0:
            return self._stream_received
        with self._lock:
            if not self._stream_mode:
                return 0
            if sample_rate and sample_rate != self.sample_rate:
                self.sample_rate = sample_rate
            self._stream_buffer.append(data)
            self._stream_received += int(data.size)
            return self._stream_received

    def finish_stream(self) -> None:
        """Marks the live stream as complete (no more chunks will arrive)."""
        with self._lock:
            self._stream_finished = True

    def set_replay_buffer(self, audio: np.ndarray) -> None:
        """
        Stores the complete clip for replay without interrupting live playback.

        Used when a streamed synthesis finishes: the stream keeps playing the
        audio it has buffered, and the finished clip becomes available for a
        second listen.
        """
        if np is None or audio is None:
            return
        with self._lock:
            self._audio_data = np.asarray(audio, dtype=np.float32).reshape(-1)

    # ------------------------------------------------------------------
    # Output stream plumbing
    # ------------------------------------------------------------------

    def _open_output_stream(self, callback) -> bool:
        """Opens a sounddevice output stream running the given callback."""
        try:
            import sounddevice as sd  # type: ignore
        except ImportError:
            logger.error("sounddevice is not available. Playback cannot start.")
            return False

        # A stream left open after natural end-of-audio would otherwise be orphaned.
        self._close_stream()

        try:
            self._stream = sd.OutputStream(
                samplerate=self.sample_rate,
                channels=1,
                dtype="float32",
                callback=callback,
                blocksize=1024,
            )
            self._stream.start()
            return True
        except Exception as e:
            logger.error("Failed to start sounddevice output stream: %s", e)
            self.state = PlaybackState.STOPPED
            return False

    def _start_stream(self) -> bool:
        opened = self._open_output_stream(self._playback_callback)
        if opened:
            self.state = PlaybackState.PLAYING
        return opened

    def _playback_callback(self, outdata, frames, time_info, status):
        """PortAudio callback serving both buffered and live-stream playback."""
        with self._lock:
            if self.state != PlaybackState.PLAYING:
                outdata.fill(0)
                return

            if self._stream_mode:
                outdata[:, 0] = self._drain_stream(frames)
                if self._stream_finished and not self._stream_buffer:
                    self.state = PlaybackState.STOPPED
                return

            # Normal (non-streaming) mode: play a single loaded array.
            if self._audio_data is None:
                outdata.fill(0)
                return

            remaining = len(self._audio_data) - self._current_sample
            if remaining <= 0:
                outdata.fill(0)
                self.state = PlaybackState.STOPPED
                self._current_sample = 0
                return

            chunk_size = min(frames, remaining)
            chunk = self._audio_data[self._current_sample : self._current_sample + chunk_size]
            outdata[:chunk_size, 0] = chunk * self.volume
            if chunk_size < frames:
                outdata[chunk_size:, 0] = 0

            self._current_sample += chunk_size

    def _drain_stream(self, frames: int) -> np.ndarray:
        """Pulls up to `frames` samples out of the live buffer (silence on underrun)."""
        out = np.zeros(frames, dtype=np.float32)
        filled = 0
        while filled < frames and self._stream_buffer:
            chunk = self._stream_buffer[0]
            remaining = int(chunk.size) - self._stream_offset
            if remaining <= 0:
                self._stream_buffer.pop(0)
                self._stream_offset = 0
                continue
            take = min(frames - filled, remaining)
            out[filled : filled + take] = (
                chunk[self._stream_offset : self._stream_offset + take] * self.volume
            )
            self._stream_offset += take
            filled += take
            if self._stream_offset >= chunk.size:
                self._stream_buffer.pop(0)
                self._stream_offset = 0

        self._stream_played += filled
        return out
