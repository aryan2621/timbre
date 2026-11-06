"""
Regression tests for bugs found in the whole-app audit.
"""

import sqlite3
import tempfile
import unittest
from pathlib import Path

import numpy as np

from app.audio.chunker import TextChunker
from app.data.database import DatabaseManager
from app.data.models import VoiceClip, VoiceProfile
from app.data.voice_repo import VoiceRepository
from app.audio.stitch import stitch_chunks


class TestChunkerRegression(unittest.TestCase):
    def test_whitespace_only_part_does_not_duplicate_text(self):
        sentence = "alpha, " + " " * 40 + ", beta"
        joined = " ".join(TextChunker._split_long_sentence(sentence, max_chars=10))
        self.assertEqual(joined.count("alpha"), 1)


class TestStitch(unittest.TestCase):
    def test_all_empty_chunks_return_empty_array(self):
        out = stitch_chunks([np.zeros(0, dtype=np.float32)] * 2, 24000)
        self.assertEqual(len(out), 0)


class TestProfileAtomicity(unittest.TestCase):
    def test_duplicate_name_leaves_no_orphan_and_raises(self):
        import app.data.database as db_mod
        with tempfile.TemporaryDirectory() as d:
            original = db_mod.db_manager
            db_mod.db_manager = DatabaseManager(Path(d) / "t.db")
            try:
                repo = VoiceRepository()
                def mk() -> VoiceProfile:
                    return VoiceProfile(
                        name="Same", language="en", consent_confirmed=True,
                        clips=[VoiceClip(file_path="x.wav", original_filename="x.wav", duration_seconds=1.0, sample_rate=24000)],
                    )
                repo.create_profile(mk())
                with self.assertRaises(sqlite3.IntegrityError):
                    repo.create_profile(mk())
                self.assertEqual(len(repo.list_all_profiles()), 1)
            finally:
                db_mod.db_manager = original


if __name__ == "__main__":
    unittest.main()
