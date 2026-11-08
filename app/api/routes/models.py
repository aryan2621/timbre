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
from app.core.secrets import hf_token_vault
from app.core.system_info import get_system_specs
from app.data.model_catalog import CATALOG_MODELS, get_model, is_model_present, model_local_path
from app.data.model_fit import BLOCKED, assess_fit

router = APIRouter()
logger = get_logger("models")


@router.get("/api/models")
def list_models() -> list[dict[str, Any]]:
    models_dir = config_manager.get_models_directory()
    specs = get_system_specs(models_dir)
    return [model_to_dict(model, models_dir, specs) for model in CATALOG_MODELS]


@router.post("/api/models/{model_id}/download")
def start_model_download(model_id: str) -> dict[str, Any]:
    model = get_model(model_id)
    if model is None:
        raise HTTPException(status_code=404, detail="Unknown model id")
    models_dir = config_manager.get_models_directory()
    fit = assess_fit(model, get_system_specs(models_dir), is_model_present(model, models_dir))
    if fit.status == BLOCKED:
        raise HTTPException(status_code=409, detail=" ".join(fit.reasons))
    if model.gated_url and hf_token_vault.get() is None:
        raise HTTPException(
            status_code=409,
            detail="Add your own Hugging Face token first. This model is gated.",
        )
    job = download_manager.start(model, models_dir)
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
