"""
Model HTTP routes.
"""

import shutil
from typing import Any

from fastapi import APIRouter, HTTPException

from app.api.downloads import download_manager
from app.api.schemas import model_to_dict
from app.core.config import config_manager
from app.core.logging_setup import get_logger
from app.data.model_catalog import CATALOG_MODELS, get_model, model_local_path

router = APIRouter()
logger = get_logger("models")


@router.get("/api/models")
def list_models() -> list[dict[str, Any]]:
    models_dir = config_manager.get_models_directory()
    return [model_to_dict(model, models_dir) for model in CATALOG_MODELS]


@router.post("/api/models/{model_id}/download")
def start_model_download(model_id: str) -> dict[str, Any]:
    model = get_model(model_id)
    if model is None:
        raise HTTPException(status_code=404, detail="Unknown model id")
    job = download_manager.start(model, config_manager.get_models_directory())
    return job.to_dict()


@router.delete("/api/models/{model_id}")
def delete_model(model_id: str) -> dict[str, Any]:
    model = get_model(model_id)
    if model is None:
        raise HTTPException(status_code=404, detail="Unknown model id")
    if download_manager.active_for_model(model_id) is not None:
        raise HTTPException(status_code=409, detail="Cancel the active download first")

    model_path = model_local_path(model, config_manager.get_models_directory())
    if not model_path.exists():
        raise HTTPException(status_code=404, detail="Model weights are not downloaded")
    shutil.rmtree(model_path)
    logger.info("Deleted model weights for %s at %s", model_id, model_path)
    return {"ok": True}
