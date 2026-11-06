"""
Data repository for Voice Profiles and their reference audio clips.
Enforces consent timestamping and profile integrity.
"""

from __future__ import annotations

import os

import app.data.database as db_mod
from app.core.logging_setup import get_logger
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
            new_id = cursor.lastrowid
            assert new_id is not None, "INSERT did not return a row id"
            profile.id = new_id

            # Same transaction as the profile row: no orphan profile if a clip insert fails.
            for clip in profile.clips or []:
                self._insert_clip(cursor, new_id, clip)

        logger.info("Created voice profile '%s' (ID: %s)", profile.name, new_id)
        return self.get_profile_by_id(new_id) or profile

    def get_profile_by_id(self, profile_id: int) -> VoiceProfile | None:
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

    def get_profile_by_name(self, name: str) -> VoiceProfile | None:
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

    def list_all_profiles(self) -> list[VoiceProfile]:
        """Returns all configured voice profiles sorted by name."""
        with db_mod.db_manager.get_cursor() as cursor:
            cursor.execute("SELECT id FROM voice_profiles ORDER BY name ASC")
            rows = cursor.fetchall()

        profiles: list[VoiceProfile] = []
        for row in rows:
            p = self.get_profile_by_id(row["id"])
            if p:
                profiles.append(p)
        return profiles

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



voice_repo = VoiceRepository()
