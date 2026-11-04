"""
Tests for chunk-by-chunk (streaming) synthesis and live playback.
"""

from __future__ import annotations

import unittest

import numpy as np

from app.audio.player import AudioPlayer, PlaybackState
from app.engines.base import EngineLicense, SynthesisParameters, TTSEngine
from app.workers.synth_worker import SynthesisWorker


class _FakeEngine(TTSEngine):
    """Engine stub that returns a deterministic tone per chunk."""

    def __init__(self, tone_length: int = 4800) -> None:
        self.tone_length = tone_length
        self.calls: list[str] = []

    @property
    def name(self) -> str:
        return "Fake Engine"

    @property
    def license_info(self) -> EngineLicense:
        return EngineLicense(
            name="MIT",
            url="https://example.invalid",
            commercial_permitted=True,
            notice="Test only.",
        )

    @property
    def supported_languages(self) -> list[str]:
        return ["en"]

    @property
    def requires_gpu_recommended(self) -> bool:
        return False

    @property
    def native_sample_rate(self) -> int:
        return 24000

    def is_available(self) -> bool:
        return True

    def is_loaded(self) -> bool:
        return True

    def load_model(self, progress_callback=None) -> bool:
        return True

    def unload_model(self) -> None:
        return None

    def clone_and_synthesize(self, text, reference_audio_path, params):
        self.calls.append(text)
        audio = np.full(self.tone_length, 0.5, dtype=np.float32)
        return audio, self.native_sample_rate

    def get_default_params(self) -> SynthesisParameters:
        return SynthesisParameters()


class TestPrepareChunk(unittest.TestCase):
    def test_first_chunk_has_no_leading_pause(self):
        chunk = np.ones(1000, dtype=np.float32)
        prepared = SynthesisWorker._prepare_chunk(
            chunk, is_first=True, sample_rate=24000, pause_ms=250
        )
        self.assertEqual(len(prepared), 1000)

    def test_subsequent_chunk_gets_leading_pause(self):
        chunk = np.ones(1000, dtype=np.float32)
        prepared = SynthesisWorker._prepare_chunk(
            chunk, is_first=False, sample_rate=24000, pause_ms=250
        )
        self.assertEqual(len(prepared), 1000 + 6000)
        self.assertTrue(np.all(prepared[:6000] == 0.0))

    def test_prepared_chunks_match_stitched_output(self):
        """Streamed chunks must concatenate into exactly the exported waveform."""
        chunks = [np.full(4000, 0.25, dtype=np.float32) for _ in range(3)]
        prepared = [
            SynthesisWorker._prepare_chunk(
                chunk,
                is_first=index == 0,
                sample_rate=24000,
                pause_ms=250,
            )
            for index, chunk in enumerate(chunks)
        ]
        stitched = SynthesisWorker._stitch_chunks_with_crossfade(
            chunks, sample_rate=24000, pause_ms=250
        )
        self.assertEqual(len(np.concatenate(prepared)), len(stitched))
        np.testing.assert_allclose(np.concatenate(prepared), stitched, atol=1e-6)

    def test_empty_chunk_is_ignored(self):
        prepared = SynthesisWorker._prepare_chunk(
            np.zeros(0, dtype=np.float32), is_first=True, sample_rate=24000
        )
        self.assertEqual(len(prepared), 0)


class TestWorkerStreaming(unittest.TestCase):
    def test_worker_emits_chunks_that_match_final_audio(self):
        engine = _FakeEngine()
        # Long enough to be split into several sentence-aware chunks.
        text = " ".join(
            f"This is sentence number {index} and it carries a fair amount of words."
            for index in range(1, 7)
        )
        worker = SynthesisWorker(
            engine=engine,
            text=text,
            reference_audio_path="unused.wav",
            params=SynthesisParameters(),
            sentence_pause_ms=250,
            streaming=True,
        )

        received: list[np.ndarray] = []
        worker.chunk_ready.connect(lambda audio, sr, idx, total: received.append(audio))

        worker.run()

        self.assertGreaterEqual(len(received), 2, "expected one signal per text chunk")
        self.assertEqual(len(engine.calls), len(received))

        concatenated = np.concatenate(received).astype(np.float32)
        # The streamed audio and the stitched export must be the same waveform.
        np.testing.assert_allclose(concatenated, worker._stitch_chunks_with_crossfade(
            [np.full(engine.tone_length, 0.5, dtype=np.float32) for _ in engine.calls],
            sample_rate=24000,
            pause_ms=250,
        ), atol=1e-6)

    def test_streaming_disabled_emits_no_chunks(self):
        engine = _FakeEngine()
        worker = SynthesisWorker(
            engine=engine,
            text="One two three. Four five six.",
            reference_audio_path="unused.wav",
            params=SynthesisParameters(),
            streaming=False,
        )

        received: list[np.ndarray] = []
        worker.chunk_ready.connect(lambda audio, sr, idx, total: received.append(audio))
        worker.run()

        self.assertEqual(received, [])


class TestBaseEngineChunkFallback(unittest.TestCase):
    def test_synthesize_chunk_defaults_to_clone_and_synthesize(self):
        engine = _FakeEngine()
        audio, sr = engine.synthesize_chunk("hello", "ref.wav", SynthesisParameters())
        self.assertEqual(sr, 24000)
        self.assertEqual(len(audio), engine.tone_length)
        self.assertEqual(engine.calls, ["hello"])


class TestChatterboxSpeed(unittest.TestCase):
    """The speed multiplier must actually change the rendered duration."""

    def test_speed_of_one_is_a_no_op(self):
        from app.engines.chatterbox_engine import ChatterboxEngine

        audio = np.full(24000, 0.25, dtype=np.float32)
        stretched = ChatterboxEngine._apply_speed(audio, 24000, 1.0)
        np.testing.assert_allclose(stretched, audio)

    def test_faster_speed_shortens_the_audio(self):
        from app.engines.chatterbox_engine import ChatterboxEngine

        timeline = np.linspace(0, 1.0, 24000, endpoint=False)
        audio = (0.3 * np.sin(2 * np.pi * 220 * timeline)).astype(np.float32)

        stretched = ChatterboxEngine._apply_speed(audio, 24000, 2.0)
        self.assertLess(len(stretched), len(audio) * 0.75)

        slowed = ChatterboxEngine._apply_speed(audio, 24000, 0.5)
        self.assertGreater(len(slowed), len(audio) * 1.25)


class TestStreamingPlayer(unittest.TestCase):
    def setUp(self) -> None:
        self.player = AudioPlayer()
        # No sound device in CI: capture the callback instead of opening a stream.
        self.callback = None
        self.player._open_output_stream = self._fake_open  # type: ignore[assignment]

    def _fake_open(self, callback) -> bool:
        self.callback = callback
        return True

    def _pull(self, frames: int = 1024) -> np.ndarray:
        out = np.zeros((frames, 1), dtype=np.float32)
        self.callback(out, frames, None, None)
        return out[:, 0]

    def test_append_chunk_is_playable(self):
        self.assertTrue(self.player.start_stream_mode(24000))
        self.player.append_chunk(np.full(480, 0.25, dtype=np.float32), 24000)

        played = self._pull(1024)
        self.assertAlmostEqual(float(played[0]), 0.25, places=5)
        self.assertAlmostEqual(float(played[479]), 0.25, places=5)
        # The rest of the block is silence (underrun).
        self.assertEqual(float(played[480]), 0.0)

    def test_position_and_duration_track_the_stream(self):
        self.player.start_stream_mode(24000)
        self.player.append_chunk(np.full(24000, 0.5, dtype=np.float32), 24000)

        self.assertAlmostEqual(self.player.duration_seconds, 1.0, places=5)
        self._pull(4096)
        self.assertAlmostEqual(self.player.current_position_seconds, 4096 / 24000, places=5)

    def test_finish_stream_stops_playback_once_drained(self):
        self.player.start_stream_mode(24000)
        self.player.append_chunk(np.ones(256, dtype=np.float32), 24000)
        self.player.finish_stream()

        self._pull(1024)
        self.assertEqual(self.player.state, PlaybackState.STOPPED)

    def test_stop_resets_stream_state(self):
        self.player.start_stream_mode(24000)
        self.player.append_chunk(np.ones(256, dtype=np.float32), 24000)
        self.player.stop()

        self.assertFalse(self.player.is_streaming)
        self.assertEqual(self.player.duration_seconds, 0.0)
        self.assertEqual(self.player.state, PlaybackState.STOPPED)

    def test_replay_buffer_survives_finished_stream(self):
        self.player.start_stream_mode(24000)
        clip = np.full(2400, 0.3, dtype=np.float32)
        self.player.append_chunk(clip, 24000)
        self.player.finish_stream()
        self.player.set_replay_buffer(clip)

        # Drain the live stream, then playback must fall back to the full clip.
        self._pull(4096)
        self.assertEqual(self.player.state, PlaybackState.STOPPED)
        self.assertTrue(self.player.play())
        self.assertEqual(self.player.state, PlaybackState.PLAYING)


if __name__ == "__main__":
    unittest.main()
