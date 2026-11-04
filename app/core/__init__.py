"""
Core application infrastructure: paths, configuration, logging, and device detection.
"""

from app.core.config import AppConfig, config_manager
from app.core.device import DeviceInfo, device_manager
from app.core.logging_setup import get_logger, setup_logging
from app.core.paths import paths

__all__ = [
    "paths",
    "setup_logging",
    "get_logger",
    "AppConfig",
    "config_manager",
    "device_manager",
    "DeviceInfo",
]

