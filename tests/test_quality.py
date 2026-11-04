"""
Unit tests for reference voice acoustic quality evaluation.
"""

import unittest

try:
    import numpy as np
except ImportError:
    np = None

from app.audio.quality import AudioQualityChecker


@unittest.skipIf(np is None, "numpy is not installed in this environment")
class TestAudioQuality(unittest.TestCase):

    def test_short_duration_warning(self):
        sr = 24000
        # 2 seconds audio (< 5s threshold)
        short_audio = np.random.uniform(-0.5, 0.5, sr * 2).astype(np.float32)
        report = AudioQualityChecker.analyze(short_audio, sr)

        self.assertFalse(report.is_acceptable)
        self.assertTrue(any("too short" in w.lower() for w in report.warnings))
        self.assertLess(report.score, 80)

    def test_clipping_detection(self):
        sr = 24000
        # Audio with hard-clipped ceiling samples
        audio = np.random.uniform(-0.5, 0.5, sr * 6).astype(np.float32)
        # Saturate 5% of samples to 1.0
        clip_indices = np.random.choice(len(audio), int(len(audio) * 0.05), replace=False)
        audio[clip_indices] = 1.0

        report = AudioQualityChecker.analyze(audio, sr)
        self.assertTrue(any("clipping" in w.lower() for w in report.warnings))
        self.assertGreater(report.clipping_ratio, 0.001)

    def test_clean_audio_high_score(self):
        sr = 24000
        # 10 seconds of speech-like dynamic signal with natural pauses
        t = np.linspace(0, 10.0, sr * 10, endpoint=False)
        carrier = np.sin(2 * np.pi * 180 * t) * 0.7
        # Modulate envelope with pauses
        mod = np.clip(np.sin(2 * np.pi * 0.5 * t), 0, 1)
        clean_speech = (carrier * mod).astype(np.float32)

        report = AudioQualityChecker.analyze(clean_speech, sr)
        self.assertGreaterEqual(report.score, 50)
        self.assertTrue(report.is_acceptable)


if __name__ == "__main__":
    unittest.main()
