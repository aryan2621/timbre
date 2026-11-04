"""
Data repository for Voice Profiles and their reference audio clips.
Enforces consent timestamping and profile integrity.
"""

from __future__ import annotations

import os
from pathlib import Path
import shutil
from typing import List, Optional

from app.core.logging_setup import get_logger
from app.core.paths import paths
import app.data.database as db_mod
from app.data.models import VoiceClip, VoiceProfile, utc_now_iso

logger = get_logger("voice_repo")


class VoiceRepository:
    """Provides CRUD operations for speaker profiles and associated audio clips."""

    def __init__(self) -> None:
        pass

    def create_profile(self, profile: VoiceProfile) -> VoiceProfile:
        """
        Creates a new speaker profile.
        Strictly enforces that consent_confirmed is True and consent_timestamp is recorded.
        """
        if not profile.consent_confirmed:
            raise ValueError("Voice profile cannot be created without explicit user consent confirmation.")

        if not profile.consent_timestamp:
            profile.consent_timestamp = utc_now_iso()

        now = utc_now_iso()
        profile.created_at = now
        profile.updated_at = now

        with db_mod.db_manager.get_cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO voice_profiles (name, language, notes, consent_confirmed, consent_timestamp, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    profile.name.strip(),
                    profile.language,
                    profile.notes,
                    1 if profile.consent_confirmed else 0,
                    profile.consent_timestamp,
                    profile.created_at,
                    profile.updated_at,
                ),
            )
            profile.id = cursor.lastrowid

            # Same transaction as the profile row: no orphan profile if a clip insert fails.
            for clip in profile.clips or []:
                self._insert_clip(cursor, profile.id, clip)

        logger.info("Created voice profile '%s' (ID: %s)", profile.name, profile.id)
        return self.get_profile_by_id(profile.id) or profile

    def get_profile_by_id(self, profile_id: int) -> Optional[VoiceProfile]:
        """Fetches a voice profile by its unique database ID, including its clips."""
        with db_mod.db_manager.get_cursor() as cursor:
            cursor.execute(
                "SELECT * FROM voice_profiles WHERE id = ?",
                (profile_id,),
            )
            row = cursor.fetchone()
            if not row:
                return None

            profile = VoiceProfile(
                id=row["id"],
                name=row["name"],
                language=row["language"],
                notes=row["notes"] or "",
                consent_confirmed=bool(row["consent_confirmed"]),
                consent_timestamp=row["consent_timestamp"],
                created_at=row["created_at"],
                updated_at=row["updated_at"],
            )

            # Query clips
            cursor.execute(
                "SELECT * FROM voice_clips WHERE profile_id = ? ORDER BY is_active DESC, id ASC",
                (profile_id,),
            )
            clip_rows = cursor.fetchall()
            profile.clips = [
                VoiceClip(
                    id=cr["id"],
                    profile_id=cr["profile_id"],
                    file_path=cr["file_path"],
                    original_filename=cr["original_filename"],
                    duration_seconds=cr["duration_seconds"],
                    sample_rate=cr["sample_rate"],
                    is_active=bool(cr["is_active"]),
                    quality_score=cr["quality_score"],
                    created_at=cr["created_at"],
                )
                for cr in clip_rows
            ]

            return profile

    def get_profile_by_name(self, name: str) -> Optional[VoiceProfile]:
        """Fetches a voice profile by its exact display name."""
        with db_mod.db_manager.get_cursor() as cursor:
            cursor.execute(
                "SELECT id FROM voice_profiles WHERE name = ?",
                (name.strip(),),
            )
            row = cursor.fetchone()
            if row:
                return self.get_profile_by_id(row["id"])
        return None

    def list_all_profiles(self) -> List[VoiceProfile]:
        """Returns all configured voice profiles sorted by name."""
        with db_mod.db_manager.get_cursor() as cursor:
            cursor.execute("SELECT id FROM voice_profiles ORDER BY name ASC")
            rows = cursor.fetchall()

        profiles: List[VoiceProfile] = []
        for row in rows:
            p = self.get_profile_by_id(row["id"])
            if p:
                profiles.append(p)
        return profiles

    def update_profile(self, profile: VoiceProfile) -> bool:
        """Updates name, language, and notes for an existing profile."""
        if not profile.id:
            return False

        profile.updated_at = utc_now_iso()
        with db_mod.db_manager.get_cursor() as cursor:
            cursor.execute(
                """
                UPDATE voice_profiles
                SET name = ?, language = ?, notes = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    profile.name.strip(),
                    profile.language,
                    profile.notes,
                    profile.updated_at,
                    profile.id,
                ),
            )
        return True

    def delete_profile(self, profile_id: int) -> bool:
        """Deletes a voice profile and its associated audio files on disk."""
        profile = self.get_profile_by_id(profile_id)
        if not profile:
            return False

        with db_mod.db_manager.get_cursor() as cursor:
            cursor.execute("DELETE FROM voice_profiles WHERE id = ?", (profile_id,))

        # Files go only after the rows are gone, so a failed DELETE can't leave a profile with no audio.
        for clip in profile.clips:
            if clip.file_path and os.path.exists(clip.file_path):
                try:
                    os.remove(clip.file_path)
                except Exception as e:
                    logger.warning("Failed to delete clip file %s: %s", clip.file_path, e)

        logger.info("Deleted profile %s (ID: %s)", profile.name, profile_id)
        return True

    def add_clip(self, profile_id: int, clip: VoiceClip) -> VoiceClip:
        """Stores a new audio clip reference for a given profile."""
        with db_mod.db_manager.get_cursor() as cursor:
            self._insert_clip(cursor, profile_id, clip)
        return clip

    @staticmethod
    def _insert_clip(cursor, profile_id: int, clip: VoiceClip) -> None:
        now = utc_now_iso()
        # If set as active, deactivate other clips for this profile
        if clip.is_active:
            cursor.execute(
                "UPDATE voice_clips SET is_active = 0 WHERE profile_id = ?",
                (profile_id,),
            )

        cursor.execute(
            """
            INSERT INTO voice_clips (profile_id, file_path, original_filename, duration_seconds, sample_rate, is_active, quality_score, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                profile_id,
                clip.file_path,
                clip.original_filename,
                clip.duration_seconds,
                clip.sample_rate,
                1 if clip.is_active else 0,
                clip.quality_score,
                now,
            ),
        )
        clip.id = cursor.lastrowid
        clip.profile_id = profile_id
        clip.created_at = now

    def set_active_clip(self, profile_id: int, clip_id: int) -> bool:
        """Sets a specific clip as the primary reference for voice synthesis."""
        with db_mod.db_manager.get_cursor() as cursor:
            cursor.execute(
                "UPDATE voice_clips SET is_active = 0 WHERE profile_id = ?",
                (profile_id,),
            )
            cursor.execute(
                "UPDATE voice_clips SET is_active = 1 WHERE id = ? AND profile_id = ?",
                (clip_id, profile_id),
            )
        return True


voice_repo = VoiceRepository()
