"""
Health routes.
"""

from typing import Any

from fastapi import APIRouter

from app.core.device import DeviceInfo, device_manager
from app.core.paths import paths
from app.engines.registry import engine_registry

router = APIRouter()


@router.get("/api/health")
def health() -> dict[str, Any]:
    # Asking an unprobed manager would import torch here and hold up the first health check.
    info = device_manager.get_device_info() if device_manager.probed else DeviceInfo("cpu", "Detecting hardware")
    return {
        "ok": True,
        "version": "0.1.1",
        "device": {
            "type": info.device_type,
            "name": info.device_name,
            "total_memory_mb": info.total_memory_mb,
            "warning": info.warning_message,
        },
        "engines": engine_registry.list_engine_names(),
        "data_dir": str(paths.data_dir),
    }
