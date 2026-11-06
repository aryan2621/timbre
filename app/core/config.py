"""
Application configuration schema and persistence.
"""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from app.core.logging_setup import get_logger
from app.core.paths import paths

logger = get_logger("config")


@dataclass
class AppConfig:
    """Strongly typed application configuration settings."""

    theme: str = "dark"  # "dark", "light", "system"
    device_preference: str = "auto"  # "auto", "cuda", "mps", "cpu"
    # Purging the CUDA/MPS allocator cache after every job forces the next
    # synthesis to re-allocate its blocks, which slows down repeated renders.
    clear_device_cache_after_job: bool = False

    # Paths overrides (empty defaults to standard paths)
    custom_models_dir: str | None = None

    # Maximum characters rendered in one pass. Generation cost grows roughly
    # quadratically with chunk length, so smaller chunks render noticeably
    # faster (and start playing sooner) at the cost of slightly more joins.
    max_chars_per_chunk: int = 200

    # Logging
    log_level: str = "INFO"

    def to_dict(self) -> dict[str, Any]:
        """Convert configuration to dictionary representation."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AppConfig:
        """Construct configuration from dictionary, ignoring unexpected keys."""
        valid_fields = cls.__dataclass_fields__.keys()
        filtered = {k: v for k, v in data.items() if k in valid_fields}
        return cls(**filtered)


class ConfigManager:
    """Manages loading, saving, and querying application settings."""

    def __init__(self, config_file: Path | None = None) -> None:
        self.config_file = config_file or paths.config_path
        self.config: AppConfig = self.load()

    def load(self) -> AppConfig:
        """Load configuration from JSON file or create with default values."""
        if not self.config_file.exists():
            logger.info("Configuration file not found at %s. Creating defaults.", self.config_file)
            default_config = AppConfig()
            self.save(default_config)
            return default_config

        try:
            with open(self.config_file, encoding="utf-8") as f:
                data = json.load(f)
            logger.debug("Configuration loaded from %s", self.config_file)
            return AppConfig.from_dict(data)
        except Exception as e:
            logger.error("Failed to load configuration from %s: %s. Using defaults.", self.config_file, e)
            return AppConfig()

    def save(self, config: AppConfig | None = None) -> bool:
        """Save active configuration to disk."""
        if config is not None:
            self.config = config

        try:
            self.config_file.parent.mkdir(parents=True, exist_ok=True)
            tmp_file = self.config_file.with_suffix(".json.tmp")
            with open(tmp_file, "w", encoding="utf-8") as f:
                json.dump(self.config.to_dict(), f, indent=2)
            os.replace(tmp_file, self.config_file)  # atomic: a crash can't truncate the settings
            logger.debug("Configuration saved successfully to %s", self.config_file)
            return True
        except Exception as e:
            logger.error("Failed to save configuration to %s: %s", self.config_file, e)
            return False

    def get_models_directory(self) -> Path:
        """Returns effective models directory (custom if configured, else default)."""
        if self.config.custom_models_dir:
            p = Path(self.config.custom_models_dir)
            p.mkdir(parents=True, exist_ok=True)
            return p
        return paths.models_dir


# Global singleton instance
config_manager = ConfigManager()

