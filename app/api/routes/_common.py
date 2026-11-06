"""
Request handling shared by the synthesis and batch routes.
"""

import random

from fastapi import HTTPException

from app.api.schemas import SynthesisParamsIn
from app.engines.base import SynthesisParameters, TTSEngine
from app.engines.registry import engine_registry


def resolve_engine(name: str) -> TTSEngine:
    """Returns a ready engine or raises the matching HTTP error."""
    engine = engine_registry.get_engine(name)
    if engine is None:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown engine '{name}'. Available: {', '.join(engine_registry.list_engine_names())}",
        )
    if not engine.is_available():
        raise HTTPException(
            status_code=409,
            detail=f"The {engine.name} engine is not installed: its Python package is missing from the API environment",
        )
    return engine


def build_params(payload: SynthesisParamsIn) -> SynthesisParameters:
    params = SynthesisParameters(**payload.model_dump())
    if params.seed < 0:
        params.seed = random.randint(1, 99_999_999)
    return params
