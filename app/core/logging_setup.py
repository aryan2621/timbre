"""
Logging configuration with rotating file handlers and console output.
"""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
import sys
from typing import Optional

from app.core.paths import paths

LOGGER_NAME = "VoiceClone"


def setup_logging(level_name: str = "INFO") -> logging.Logger:
    """
    Initializes application logging with rotating file handler and console output.
    """
    numeric_level = getattr(logging, level_name.upper(), logging.INFO)
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(numeric_level)

    # Avoid duplicate handlers on re-init
    for old in list(logger.handlers):
        old.close()
        logger.removeHandler(old)

    # Formatter
    formatter = logging.Formatter(
        fmt="[%(asctime)s] [%(levelname)s] [%(threadName)s] %(name)s (%(filename)s:%(lineno)d): %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(numeric_level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # Rotating File Handler (10 MB per file, max 5 backups)
    log_file = paths.log_file_path
    try:
        file_handler = RotatingFileHandler(
            filename=str(log_file),
            maxBytes=10 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
        )
        file_handler.setLevel(numeric_level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except Exception as e:
        print(f"Warning: Failed to initialize file logger at {log_file}: {e}", file=sys.stderr)

    logger.info("Logging initialized. Writing logs to: %s", log_file)
    return logger


def get_logger(module_name: Optional[str] = None) -> logging.Logger:
    """
    Returns a child logger scoped to a specific module or component.
    """
    if module_name:
        return logging.getLogger(f"{LOGGER_NAME}.{module_name}")
    return logging.getLogger(LOGGER_NAME)

