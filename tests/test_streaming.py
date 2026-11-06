"""
Tests for chunk-by-chunk (streaming) synthesis and live playback.
"""

from __future__ import annotations

import unittest

import numpy as np

from app.audio.stitch import prepare_chunk, stitch_chunks
from app.engines.base import EngineLicense, SynthesisParameters, TTSEngine


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
        prepared = prepare_chunk(
            chunk, is_first=True, sample_rate=24000, pause_ms=250
        )
        self.assertEqual(len(prepared), 1000)

    def test_subsequent_chunk_gets_leading_pause(self):
        chunk = np.ones(1000, dtype=np.float32)
        prepared = prepare_chunk(
            chunk, is_first=False, sample_rate=24000, pause_ms=250
        )
        self.assertEqual(len(prepared), 1000 + 6000)
        self.assertTrue(np.all(prepared[:6000] == 0.0))

    def test_prepared_chunks_match_stitched_output(self):
        """Streamed chunks must concatenate into exactly the exported waveform."""
        chunks = [np.full(4000, 0.25, dtype=np.float32) for _ in range(3)]
        prepared = [
            prepare_chunk(
                chunk,
                is_first=index == 0,
                sample_rate=24000,
                pause_ms=250,
            )
            for index, chunk in enumerate(chunks)
        ]
        stitched = stitch_chunks(
            chunks, sample_rate=24000, pause_ms=250
        )
        self.assertEqual(len(np.concatenate(prepared)), len(stitched))
        np.testing.assert_allclose(np.concatenate(prepared), stitched, atol=1e-6)

    def test_empty_chunk_is_ignored(self):
        prepared = prepare_chunk(
            np.zeros(0, dtype=np.float32), is_first=True, sample_rate=24000
        )
        self.assertEqual(len(prepared), 0)


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


if __name__ == "__main__":
    unittest.main()
