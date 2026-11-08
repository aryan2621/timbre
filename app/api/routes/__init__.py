"""
FastAPI router aggregating all API sub-routers.

Sub-routers register their routes with fully-qualified paths (e.g. "/api/health")
and are included in registration order to preserve the original route matching
order.
"""

from fastapi import APIRouter

from app.api.routes import (
    agents,
    batch,
    credentials,
    downloads,
    engines,
    health,
    history,
    jobs,
    models,
    settings,
    sounds,
    synthesis,
    system,
    voices,
)

api_router = APIRouter()

api_router.include_router(voices.router)
api_router.include_router(agents.router)
api_router.include_router(history.router)
api_router.include_router(jobs.router)
api_router.include_router(synthesis.router)
api_router.include_router(sounds.router)
api_router.include_router(batch.router)
api_router.include_router(models.router)
api_router.include_router(downloads.router)
api_router.include_router(settings.router)
api_router.include_router(credentials.router)
api_router.include_router(system.router)
api_router.include_router(engines.router)
api_router.include_router(health.router)
