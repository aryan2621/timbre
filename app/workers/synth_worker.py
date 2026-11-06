"""
Background worker thread for asynchronous speech synthesis, chunking,
crossfade audio stitching, progress reporting, and cancellation.
"""

from __future__ import annotations

import time
from pathlib import Path

try:
    import numpy as np
except ImportError:
    np = None

# Safe PySide6 imports with headless fallback
try:
    from PySide6.QtCore import QObject, QThread, Signal  # type: ignore
except ImportError:
    # Dummy mock for non-GUI / headless test environments
    class Signal:
        def __init__(self, *args): pass
        def emit(self, *args): pass

    class QObject:
        pass

    class QThread:
        def start(self): pass
        def wait(self): pass
        def isRunning(self): return False

from app.audio.chunker import TextChunker
from app.core.config import config_manager
from app.core.device import device_manager
from app.core.logging_setup import get_logger
from app.core.paths import paths
from app.engines.base import SynthesisParameters, TTSEngine

logger = get_logger("synth_worker")


class SynthesisWorker(QThread):
    """Executes long-form TTS generation in a background thread with crossfading."""

    # Qt Signals for worker-to-UI communication
    progress_updated = Signal(int, int, float, str)  # (current_chunk, total_chunks, percent, eta_text)
    status_updated = Signal(str)                     # message string
    chunk_ready = Signal(object, int, int, int)      # (audio_array, sample_rate, chunk_index, total_chunks) — streamed per chunk
    generation_finished = Signal(object, int, str, float)  # (audio_array, sample_rate, temp_path, elapsed_sec)
    generation_failed = Signal(str)                  # user-friendly error message

    def __init__(
        self,
        engine: TTSEngine,
        text: str,
        reference_audio_path: str | Path,
        params: SynthesisParameters,
        sentence_pause_ms: int = 250,
        parent: QObject | None = None,
        preview_dir: Path | None = None,
        streaming: bool = True,
    ) -> None:
        super().__init__(parent)
        self.engine = engine
        self.text = text
        self.reference_audio_path = reference_audio_path
        self.params = params
        self.sentence_pause_ms = sentence_pause_ms
        self.preview_dir = preview_dir or paths.history_dir  # history audio must outlive the cache
        self.streaming = streaming
        self._is_cancelled = False

    def cancel(self) -> None:
        """Signals the background thread to cancel active generation."""
        logger.info("Cancellation requested for synthesis task.")
        self._is_cancelled = True

    def run(self) -> None:
        """Thread execution loop."""
        start_time = time.time()
        self._is_cancelled = False
        failed = False

        try:
            self.status_updated.emit(f"Preparing speech model ({self.engine.name})")
            with self.engine.lock:
                if not self.engine.is_loaded() and not self.engine.load_model():
                    self.generation_failed.emit(f"Could not load the {self.engine.name} model.")
                    return

            if self._is_cancelled:
                self.status_updated.emit("Generation cancelled.")
                return

            # Chunk text into sentence-aware blocks. Smaller chunks render
            # faster and start playing sooner; see AppConfig.max_chars_per_chunk.
            chunks: list[str] = TextChunker.chunk_text(
                self.text,
                max_chars_per_chunk=config_manager.config.max_chars_per_chunk,
            )
            if not chunks:
                self.generation_failed.emit("Input text is empty or invalid.")
                return

            total_chunks = len(chunks)
            logger.info("Starting synthesis for %d text chunks.", total_chunks)

            rendered_audio_chunks: list[np.ndarray] = []
            chunk_sample_rate = self.engine.native_sample_rate
            chunk_times: list[float] = []
            emitted_any = False

            for idx, chunk_text in enumerate(chunks):
                if self._is_cancelled:
                    logger.info("Synthesis cancelled at chunk %d/%d.", idx + 1, total_chunks)
                    self.status_updated.emit("Generation cancelled by user.")
                    return

                chunk_start = time.time()
                self.status_updated.emit(f"Synthesizing sentence {idx + 1} of {total_chunks}")

                # Synthesize individual chunk
                with self.engine.lock:
                    audio, sr = self.engine.synthesize_chunk(
                        text=chunk_text,
                        reference_audio_path=self.reference_audio_path,
                        params=self.params,
                    )
                chunk_sample_rate = sr
                rendered_audio_chunks.append(audio)

                # Emit this chunk immediately so the UI can play it without
                # waiting for the remaining chunks (streaming playback). The
                # chunk is prepared exactly like the stitched export, so what
                # you hear and what you save are the same waveform.
                if self.streaming and len(audio) > 0:
                    prepared = self._prepare_chunk(
                        audio,
                        is_first=not emitted_any,
                        sample_rate=chunk_sample_rate,
                        pause_ms=self.sentence_pause_ms,
                    )
                    emitted_any = True
                    self.chunk_ready.emit(prepared, chunk_sample_rate, idx, total_chunks)

                # Track time and calculate ETA
                elapsed_chunk = time.time() - chunk_start
                chunk_times.append(elapsed_chunk)
                avg_chunk_time = sum(chunk_times) / len(chunk_times)
                remaining_chunks = total_chunks - (idx + 1)
                eta_seconds = remaining_chunks * avg_chunk_time

                eta_str = f"{int(eta_seconds)}s" if eta_seconds < 60 else f"{int(eta_seconds // 60)}m {int(eta_seconds % 60)}s"
                progress_percent = ((idx + 1) / total_chunks) * 100.0

                self.progress_updated.emit(idx + 1, total_chunks, progress_percent, eta_str)

            if self._is_cancelled:
                self.status_updated.emit("Generation cancelled.")
                return

            self.status_updated.emit("Stitching audio chunks with crossfades")
            stitched_audio = self._stitch_chunks_with_crossfade(
                rendered_audio_chunks,
                sample_rate=chunk_sample_rate,
                pause_ms=self.sentence_pause_ms,
            )

            # Save temporary preview file
            temp_output = self.preview_dir / f"synth_{int(time.time() * 1000)}.wav"
            try:
                import soundfile as sf  # type: ignore
                temp_output.parent.mkdir(parents=True, exist_ok=True)
                sf.write(str(temp_output), stitched_audio, chunk_sample_rate)
                preview_path = str(temp_output)
            except Exception as e:
                logger.warning("Failed to write preview WAV: %s", e)
                preview_path = ""  # don't hand out a path to a file that doesn't exist

            total_elapsed = time.time() - start_time
            logger.info("Synthesis finished in %.2f seconds.", total_elapsed)

            self.generation_finished.emit(
                stitched_audio,
                chunk_sample_rate,
                preview_path,
                total_elapsed,
            )

        except Exception as e:
            failed = True
            logger.exception("Synthesis failed with unhandled exception: %s", e)
            if "out of memory" in str(e).lower() or "cuda oom" in str(e).lower():
                user_msg = device_manager.format_oom_message(e)
            else:
                user_msg = f"Generation failed: {str(e)}"
            self.generation_failed.emit(user_msg)
        finally:
            # Purging the CUDA/MPS cache after every job forces the next run to
            # re-allocate its blocks, which noticeably slows consecutive
            # generations. Only free on failure (OOM) or when explicitly asked.
            if failed or config_manager.config.clear_device_cache_after_job:
                device_manager.clear_cache()

    @staticmethod
    def _prepare_chunk(
        chunk: np.ndarray,
        is_first: bool,
        sample_rate: int,
        pause_ms: int = 250,
        crossfade_ms: int = 40,
    ) -> np.ndarray:
        """
        Prepares one rendered chunk for playback: an optional leading sentence
        pause plus short edge fades that remove clicks at chunk boundaries.

        Chunks prepared this way concatenate into exactly the same waveform as
        :meth:`_stitch_chunks_with_crossfade`, so streamed playback and the
        exported file are identical.
        """
        if np is None:
            return chunk

        cur = np.asarray(chunk, dtype=np.float32).reshape(-1)
        if cur.size == 0:
            return np.zeros(0, dtype=np.float32)

        pause_samples = int((pause_ms / 1000.0) * sample_rate)
        crossfade_samples = int((crossfade_ms / 1000.0) * sample_rate)

        if crossfade_samples > 0 and len(cur) > crossfade_samples * 2:
            # Apply brief edge crossfade if long enough
            fade_in = np.linspace(0.0, 1.0, crossfade_samples, dtype=np.float32)
            fade_out = np.linspace(1.0, 0.0, crossfade_samples, dtype=np.float32)
            cur = cur.copy()
            cur[:crossfade_samples] *= fade_in
            cur[-crossfade_samples:] *= fade_out

        if is_first or pause_samples <= 0:
            return cur.astype(np.float32)

        pause_silence = np.zeros(pause_samples, dtype=np.float32)
        return np.concatenate([pause_silence, cur]).astype(np.float32)

    @staticmethod
    def _stitch_chunks_with_crossfade(
        chunks: list[np.ndarray],
        sample_rate: int,
        pause_ms: int = 250,
        crossfade_ms: int = 40,
    ) -> np.ndarray:
        """
        Stitches audio chunks with a natural pause and smooth linear crossfades
        to eliminate phase discontinuities and clicks.
        """
        prepared: list[np.ndarray] = []
        for chunk in chunks:
            if len(chunk) == 0:
                continue
            prepared.append(
                SynthesisWorker._prepare_chunk(
                    chunk,
                    is_first=not prepared,
                    sample_rate=sample_rate,
                    pause_ms=pause_ms,
                    crossfade_ms=crossfade_ms,
                )
            )

        if not prepared:
            return np.zeros(0, dtype=np.float32)
        if len(prepared) == 1:
            return prepared[0]

        return np.concatenate(prepared).astype(np.float32)
