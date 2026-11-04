"""
Unit tests for audio preprocessing (mono conversion, resampling, VAD, normalization).
"""

import unittest

try:
    import numpy as np
except ImportError:
    np = None

from app.audio.preprocess import AudioPreprocessor


@unittest.skipIf(np is None, "numpy is not installed in this environment")
class TestAudioPreprocessor(unittest.TestCase):

    def test_to_mono_from_stereo(self):
        # Create 2-channel stereo signal
        left = np.full(1000, 0.4, dtype=np.float32)
        right = np.full(1000, 0.6, dtype=np.float32)
        stereo = np.stack([left, right], axis=-1)

        mono = AudioPreprocessor.to_mono(stereo)
        self.assertEqual(mono.ndim, 1)
        self.assertEqual(len(mono), 1000)
        self.assertAlmostEqual(mono[0], 0.5, places=5)

    def test_resample_duration_preservation(self):
        # 1 second of 48000Hz audio
        sr_orig = 48000
        sr_target = 24000
        t = np.linspace(0, 1.0, sr_orig, endpoint=False)
        audio = np.sin(2 * np.pi * 440 * t).astype(np.float32)

        resampled = AudioPreprocessor.resample(audio, sr_orig, sr_target)
        self.assertEqual(len(resampled), sr_target)

    def test_vad_silence_trimming(self):
        sr = 24000
        # 1 sec silence, 1 sec sine tone, 1 sec silence
        silence = np.zeros(sr, dtype=np.float32)
        tone = np.sin(2 * np.pi * 440 * np.linspace(0, 1.0, sr)).astype(np.float32) * 0.8
        composite = np.concatenate([silence, tone, silence])

        trimmed = AudioPreprocessor.trim_silence_vad(composite, sr, threshold_db=-30.0)
        # Trimmed audio should be significantly shorter than composite (3.0s)
        self.assertLess(len(trimmed), len(composite))
        self.assertGreater(len(trimmed), int(sr * 0.8))

    def test_loudness_normalization(self):
        sr = 24000
        quiet_signal = np.sin(2 * np.pi * 300 * np.linspace(0, 1.0, sr)).astype(np.float32) * 0.05
        normalized = AudioPreprocessor.normalize_loudness(quiet_signal, sr, target_lufs=-23.0)

        # Output should have higher peak amplitude than original quiet signal
        self.assertGreater(np.max(np.abs(normalized)), np.max(np.abs(quiet_signal)))
        # Guard should prevent clipping
        self.assertLessEqual(np.max(np.abs(normalized)), 1.0)


if __name__ == "__main__":
    unittest.main()
