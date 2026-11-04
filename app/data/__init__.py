"""
Data persistence layer for database management, voice profiles, and generation history.
"""

from app.data.database import DatabaseManager, db_manager
from app.data.history_repo import HistoryRepository, history_repo
from app.data.models import (
    BatchJob,
    HistoryEntry,
    ModelMetadata,
    QualityReport,
    VoiceClip,
    VoiceProfile,
)
from app.data.voice_repo import VoiceRepository, voice_repo

__all__ = [
    "DatabaseManager",
    "db_manager",
    "VoiceProfile",
    "VoiceClip",
    "HistoryEntry",
    "ModelMetadata",
    "BatchJob",
    "QualityReport",
    "VoiceRepository",
    "voice_repo",
    "HistoryRepository",
    "history_repo",
]

