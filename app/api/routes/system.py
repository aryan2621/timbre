from typing import Any

from fastapi import APIRouter

from app.core.config import config_manager
from app.core.system_info import get_system_specs

router = APIRouter()


@router.get("/api/system")
def system_specs() -> dict[str, Any]:
    return get_system_specs(config_manager.get_models_directory()).to_dict()
