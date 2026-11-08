"""
Data repository for speech synthesis history logging and retrieval.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import app.data.database as db_mod
from app.core.logging_setup import get_logger
from app.core.paths import paths
from app.data.models import HistoryEntry, utc_now_iso

logger = get_logger("history_repo")


def _remove_owned_audio(audio_path: str | None) -> None:
    """Deletes a render, but only inside our own history folder.

    Batch renders can live in a folder the user picked; removing a history row
    must never delete their exported files.
    """
    if not audio_path or not os.path.exists(audio_path):
        return
    try:
        if not Path(audio_path).resolve().is_relative_to(paths.history_dir.resolve()):
            return
        os.remove(audio_path)
    except OSError as e:
        logger.warning("Failed to remove history audio file %s: %s", audio_path, e)


class HistoryRepository:
    """Manages the persistence and retrieval of generated audio generations."""

    def add_entry(self, entry: HistoryEntry) -> HistoryEntry:
        """Records a new audio generation event into the database."""
        if not entry.created_at:
            entry.created_at = utc_now_iso()

        with db_mod.db_manager.get_cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO history (voice_id, voice_name, engine_name, prompt_text, parameters_json, seed, audio_path, duration_seconds, sample_rate, created_at, kind)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    entry.voice_id,
                    entry.voice_name,
                    entry.engine_name,
                    entry.prompt_text,
                    entry.parameters_json,
                    entry.seed,
                    entry.audio_path,
                    entry.duration_seconds,
                    entry.sample_rate,
                    entry.created_at,
                    entry.kind,
                ),
            )
            entry.id = cursor.lastrowid
        logger.debug("Logged synthesis history entry ID: %s", entry.id)
        return entry

    def get_entry_by_id(self, entry_id: int) -> HistoryEntry | None:
        """Retrieves a single generation record by its database ID."""
        with db_mod.db_manager.get_cursor() as cursor:
            cursor.execute("SELECT * FROM history WHERE id = ?", (entry_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return self._row_to_entry(row)

    def list_recent(self, limit: int = 100, offset: int = 0) -> list[HistoryEntry]:
        """Returns the most recent generation entries."""
        with db_mod.db_manager.get_cursor() as cursor:
            cursor.execute(
                "SELECT * FROM history ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (limit, offset),
            )
            rows = cursor.fetchall()
            return [self._row_to_entry(r) for r in rows]

    def search(self, query: str, limit: int = 50) -> list[HistoryEntry]:
        """Filters history items matching query in prompt_text or voice_name."""
        q = f"%{query.strip()}%"
        with db_mod.db_manager.get_cursor() as cursor:
            cursor.execute(
                """
                SELECT * FROM history
                WHERE prompt_text LIKE ? OR voice_name LIKE ? OR engine_name LIKE ?
                ORDER BY created_at DESC LIMIT ?
                """,
                (q, q, q, limit),
            )
            rows = cursor.fetchall()
            return [self._row_to_entry(r) for r in rows]

    def delete_entry(self, entry_id: int, delete_file: bool = True) -> bool:
        """Deletes a history record and optionally removes the rendered audio file."""
        entry = self.get_entry_by_id(entry_id)
        if not entry:
            return False

        if delete_file:
            _remove_owned_audio(entry.audio_path)

        with db_mod.db_manager.get_cursor() as cursor:
            cursor.execute("DELETE FROM history WHERE id = ?", (entry_id,))
        return True

    def clear_all(self, delete_files: bool = True) -> int:
        """Clears all history records."""
        with db_mod.db_manager.get_cursor() as cursor:
            cursor.execute("SELECT id, audio_path FROM history")
            rows = cursor.fetchall()
            cursor.execute("DELETE FROM history")
        if delete_files:
            for row in rows:
                _remove_owned_audio(row["audio_path"])
        return len(rows)

    @staticmethod
    def _row_to_entry(row: Any) -> HistoryEntry:
        return HistoryEntry(
            id=row["id"],
            voice_id=row["voice_id"],
            voice_name=row["voice_name"],
            engine_name=row["engine_name"],
            prompt_text=row["prompt_text"],
            parameters_json=row["parameters_json"],
            seed=row["seed"],
            audio_path=row["audio_path"],
            duration_seconds=row["duration_seconds"],
            sample_rate=row["sample_rate"],
            created_at=row["created_at"],
            kind=row["kind"],
        )


history_repo = HistoryRepository()
