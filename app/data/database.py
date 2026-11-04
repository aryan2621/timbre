"""
Thread-safe SQLite database manager with WAL mode and schema initialization.
"""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
import sqlite3
import threading
from typing import Generator, Optional

from app.core.logging_setup import get_logger
from app.core.paths import paths

logger = get_logger("database")


SCHEMA_SQL = """
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;

CREATE TABLE IF NOT EXISTS voice_profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    language TEXT NOT NULL DEFAULT 'en',
    notes TEXT DEFAULT '',
    consent_confirmed INTEGER NOT NULL DEFAULT 0,
    consent_timestamp TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS voice_clips (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id INTEGER NOT NULL,
    file_path TEXT NOT NULL,
    original_filename TEXT NOT NULL,
    duration_seconds REAL NOT NULL,
    sample_rate INTEGER NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1,
    quality_score INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    FOREIGN KEY(profile_id) REFERENCES voice_profiles(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    voice_id INTEGER,
    voice_name TEXT NOT NULL,
    engine_name TEXT NOT NULL,
    prompt_text TEXT NOT NULL,
    parameters_json TEXT NOT NULL DEFAULT '{}',
    seed INTEGER NOT NULL DEFAULT -1,
    audio_path TEXT NOT NULL,
    duration_seconds REAL NOT NULL DEFAULT 0.0,
    sample_rate INTEGER NOT NULL DEFAULT 24000,
    created_at TEXT NOT NULL,
    FOREIGN KEY(voice_id) REFERENCES voice_profiles(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS model_catalog (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    version TEXT NOT NULL,
    license_name TEXT NOT NULL,
    commercial_allowed INTEGER NOT NULL DEFAULT 0,
    license_notice TEXT NOT NULL,
    download_url TEXT NOT NULL,
    expected_sha256 TEXT NOT NULL,
    total_bytes INTEGER NOT NULL DEFAULT 0,
    local_dir TEXT NOT NULL,
    is_downloaded INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_voice_clips_profile ON voice_clips(profile_id);
CREATE INDEX IF NOT EXISTS idx_history_created ON history(created_at DESC);
"""


class DatabaseManager:
    """Manages SQLite database connections, schema updates, and transactions."""

    def __init__(self, db_path: Optional[Path] = None) -> None:
        self.db_path = db_path or paths.database_path
        self._local = threading.local()
        self._lock = threading.Lock()
        self.initialize_schema()

    def _get_connection(self) -> sqlite3.Connection:
        """Retrieves or creates a thread-local SQLite connection with dictionary row access."""
        if not hasattr(self._local, "conn") or self._local.conn is None:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(
                str(self.db_path),
                timeout=30.0,
                check_same_thread=False,
            )
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA foreign_keys = ON;")
            conn.execute("PRAGMA journal_mode = WAL;")
            self._local.conn = conn
        return self._local.conn

    @contextmanager
    def get_cursor(self) -> Generator[sqlite3.Cursor, None, None]:
        """Context manager yielding a database cursor inside an auto-committing transaction."""
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            yield cursor
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error("Database transaction rolled back due to error: %s", e)
            raise
        finally:
            cursor.close()

    def initialize_schema(self) -> None:
        """Executes DDL commands to ensure all tables and indexes exist."""
        with self._lock:
            try:
                conn = self._get_connection()
                conn.executescript(SCHEMA_SQL)
                conn.commit()
                logger.info("Database schema initialized successfully at %s", self.db_path)
            except Exception as e:
                logger.critical("Failed to initialize database schema: %s", e)
                raise


db_manager = DatabaseManager()

