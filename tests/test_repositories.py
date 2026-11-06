"""
Unit tests for SQLite database management, voice repository, and history repository.
"""

import tempfile
import unittest
from pathlib import Path

from app.data.database import DatabaseManager
from app.data.history_repo import HistoryRepository
from app.data.models import HistoryEntry, VoiceClip, VoiceProfile
from app.data.voice_repo import VoiceRepository


class TestRepositories(unittest.TestCase):

    def setUp(self):
        # Create temporary database
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test.db"

        # Patch db_manager
        import app.data.database as db_mod
        self.original_db = db_mod.db_manager
        self.test_db = DatabaseManager(self.db_path)
        db_mod.db_manager = self.test_db

        self.voice_repo = VoiceRepository()
        self.history_repo = HistoryRepository()

    def tearDown(self):
        import app.data.database as db_mod
        db_mod.db_manager = self.original_db
        self.temp_dir.cleanup()

    def test_consent_enforcement_on_profile_creation(self):
        # Must fail if consent_confirmed is False
        profile = VoiceProfile(
            name="Unconsented Voice",
            language="en",
            consent_confirmed=False,
        )
        with self.assertRaises(ValueError):
            self.voice_repo.create_profile(profile)

    def test_profile_creation_and_retrieval(self):
        profile = VoiceProfile(
            name="Alice Speaker",
            language="en",
            notes="Calm tone",
            consent_confirmed=True,
            consent_timestamp="2026-11-02T12:00:00Z",
        )
        created = self.voice_repo.create_profile(profile)
        self.assertIsNotNone(created.id)

        fetched = self.voice_repo.get_profile_by_id(created.id)
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.name, "Alice Speaker")
        self.assertTrue(fetched.consent_confirmed)

    def test_clip_addition_and_active_toggle(self):
        profile = self.voice_repo.create_profile(VoiceProfile(
            name="Bob Speaker",
            language="en",
            consent_confirmed=True,
            consent_timestamp="2026-11-02T12:00:00Z",
        ))

        self.voice_repo.add_clip(profile.id, VoiceClip(
            file_path="/tmp/clip1.wav",
            original_filename="clip1.wav",
            duration_seconds=10.0,
            sample_rate=24000,
            is_active=True,
            quality_score=85,
        ))

        clip2 = self.voice_repo.add_clip(profile.id, VoiceClip(
            file_path="/tmp/clip2.wav",
            original_filename="clip2.wav",
            duration_seconds=12.0,
            sample_rate=24000,
            is_active=False,
            quality_score=90,
        ))

        # Test switching active clip
        self.voice_repo.set_active_clip(profile.id, clip2.id)
        reloaded = self.voice_repo.get_profile_by_id(profile.id)
        self.assertEqual(reloaded.primary_audio_path, "/tmp/clip2.wav")

    def test_history_logging_and_search(self):
        profile = self.voice_repo.create_profile(VoiceProfile(
            name="Charlie Speaker",
            language="en",
            consent_confirmed=True,
            consent_timestamp="2026-11-02T12:00:00Z",
        ))

        entry = HistoryEntry(
            voice_id=profile.id,
            voice_name="Charlie Speaker",
            engine_name="Chatterbox TTS",
            prompt_text="The quick brown fox jumps over the lazy dog.",
            parameters_json="{}",
            seed=42,
            audio_path="/tmp/output.wav",
            duration_seconds=3.2,
            sample_rate=24000,
        )
        saved = self.history_repo.add_entry(entry)
        self.assertIsNotNone(saved.id)

        # Search by keyword
        results = self.history_repo.search("brown fox")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].voice_name, "Charlie Speaker")


if __name__ == "__main__":
    unittest.main()
