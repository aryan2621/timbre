"""
Settings HTTP routes.
"""

from typing import Any

from fastapi import APIRouter, Body, HTTPException

from app.core.config import AppConfig, config_manager
from app.core.logging_setup import get_logger

router = APIRouter()
logger = get_logger("settings")


@router.get("/api/settings")
def get_settings() -> dict[str, Any]:
    return config_manager.config.to_dict()


@router.put("/api/settings")
def update_settings(payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
    valid = AppConfig.__dataclass_fields__.keys()
    filtered = {key: value for key, value in payload.items() if key in valid}
    merged = {**config_manager.config.to_dict(), **filtered}
    next_config = AppConfig.from_dict(merged)
    if not config_manager.save(next_config):
        raise HTTPException(status_code=500, detail="Could not persist settings")
    logger.info("Settings updated via API: %s", ", ".join(sorted(filtered)) or "no changes")
    return config_manager.config.to_dict()
