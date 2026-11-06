"""
Paths configuration for VoiceClone Studio.
Resolves application data, cache, configuration, models, logs, and export directories
using standard cross-platform platformdirs conventions, with robust fallback handling.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

APP_NAME = "VoiceCloneStudio"
APP_AUTHOR = "VoiceClone"


class AppPaths:
    """Manages all standard file system paths used by the application."""

    def __init__(self) -> None:
        try:
            import platformdirs  # type: ignore
            self._user_data_dir = Path(platformdirs.user_data_dir(APP_NAME, APP_AUTHOR))
            self._user_config_dir = Path(platformdirs.user_config_dir(APP_NAME, APP_AUTHOR))
            self._user_cache_dir = Path(platformdirs.user_cache_dir(APP_NAME, APP_AUTHOR))
            self._user_log_dir = Path(platformdirs.user_log_dir(APP_NAME, APP_AUTHOR))
        except (ImportError, Exception):
            home = Path.home()
            self._user_data_dir = home / ".voiceclone" / "data"
            self._user_config_dir = home / ".voiceclone" / "config"
            self._user_cache_dir = home / ".voiceclone" / "cache"
            self._user_log_dir = home / ".voiceclone" / "logs"

        # Ensure core directories exist with sandbox/permission fallback
        self.ensure_directories()

    def ensure_directories(self) -> None:
        """Create all necessary base directories on disk if they do not exist."""
        try:
            for path in [
                self.data_dir,
                self.config_dir,
                self.cache_dir,
                self.log_dir,
                self.models_dir,
                self.voices_dir,
                self.history_dir,
                self.exports_dir,
                self.temp_dir,
            ]:
                path.mkdir(parents=True, exist_ok=True)
        except (PermissionError, OSError):
            # Fallback to /tmp if home dir is not writeable in restricted sandbox environments
            tmp_root = Path(tempfile.gettempdir()) / "VoiceCloneStudio"
            self._user_data_dir = tmp_root / "data"
            self._user_config_dir = tmp_root / "config"
            self._user_cache_dir = tmp_root / "cache"
            self._user_log_dir = tmp_root / "logs"

            for path in [
                self.data_dir,
                self.config_dir,
                self.cache_dir,
                self.log_dir,
                self.models_dir,
                self.voices_dir,
                self.history_dir,
                self.exports_dir,
                self.temp_dir,
            ]:
                path.mkdir(parents=True, exist_ok=True)

    @property
    def data_dir(self) -> Path:
        """Directory for persistent user data (database, voice profiles)."""
        return self._user_data_dir

    @property
    def config_dir(self) -> Path:
        """Directory for user configuration files."""
        return self._user_config_dir

    @property
    def cache_dir(self) -> Path:
        """Directory for temporary cached downloads and processed audio."""
        return self._user_cache_dir

    @property
    def log_dir(self) -> Path:
        """Directory for rotating log files."""
        return self._user_log_dir

    @property
    def models_dir(self) -> Path:
        """Directory for downloaded neural TTS weights."""
        return self._user_data_dir / "models"

    @property
    def voices_dir(self) -> Path:
        """Directory for stored voice profile audio clips."""
        return self._user_data_dir / "voices"

    @property
    def history_dir(self) -> Path:
        """Directory for rendered synthesis history audio files."""
        return self._user_data_dir / "history_audio"

    @property
    def exports_dir(self) -> Path:
        """Default directory for exported audio files."""
        return self._user_data_dir / "exports"

    @property
    def temp_dir(self) -> Path:
        """Temporary working directory for recording and processing buffers."""
        return self._user_cache_dir / "tmp"

    @property
    def database_path(self) -> Path:
        """File path to the SQLite application database."""
        return self._user_data_dir / "voiceclone.db"

    @property
    def config_path(self) -> Path:
        """File path to the user configuration JSON file."""
        return self._user_config_dir / "config.json"

    @property
    def log_file_path(self) -> Path:
        """File path to the primary rotating application log."""
        return self._user_log_dir / "voiceclone.log"


# Global singleton instance
paths = AppPaths()
