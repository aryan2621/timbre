"""
Engine listing routes.
"""

from typing import Any

from fastapi import APIRouter

from app.api.schemas import engine_to_dict
from app.engines.registry import engine_registry

router = APIRouter()


@router.get("/api/engines")
def list_engines() -> list[dict[str, Any]]:
    return [engine_to_dict(engine) for engine in engine_registry.get_all_engines()]
