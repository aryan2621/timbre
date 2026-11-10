"""
FastAPI sidecar for VoiceClone Studio.

The Tauri/React frontend talks to this service over loopback HTTP. This module
is the composition root: it wires the FastAPI app, middleware, lifespan and
routers. Business logic lives in ``app.services`` and HTTP contracts live in
``app.api.schemas`` / ``app.api.routes``.
"""

from __future__ import annotations

import os
import secrets
import threading
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import api_router
from app.core.config import AppConfig, config_manager
from app.core.logging_setup import get_logger, setup_logging
from app.engines.registry import engine_registry, sound_registry
from app.services import agent_service

logger = get_logger("api")

API_VERSION = "0.1.4"
DEFAULT_PORT = 8756


# Re-exported for backwards compatibility with existing imports/tests.
from app.core.paths import paths  # noqa: E402,F401
from app.data.history_repo import history_repo  # noqa: E402,F401
from app.data.voice_repo import voice_repo  # noqa: E402,F401


@asynccontextmanager
async def lifespan(_: FastAPI):
    setup_logging(config_manager.config.log_level)
    logger.info("VoiceClone API %s starting on loopback.", API_VERSION)
    if not os.environ.get("VOICECLONE_API_TOKEN"):
        logger.warning("VOICECLONE_API_TOKEN is not set: the API accepts any local caller.")
    threading.Thread(target=engine_registry.preload, name="voice-preload", daemon=True).start()
    try:
        yield
    finally:
        try:
            engine_registry.unload_all()
            sound_registry.unload_all()
            agent_service.stop_all()
        except Exception:  # pragma: no cover
            logger.debug("Engine unload during shutdown failed", exc_info=True)
        logger.info("VoiceClone API stopped.")


app = FastAPI(title="VoiceClone Studio API", version=API_VERSION, lifespan=lifespan)

app.add_middleware(GZipMiddleware, minimum_size=1024)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:1420",
        "http://127.0.0.1:1420",
        "tauri://localhost",
        "http://tauri.localhost",
        "https://tauri.localhost",
    ],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

TOKEN_HEADER = "x-voiceclone-token"
_OPEN_PATHS = {"/api/health"}


@app.middleware("http")
async def require_token(request: Request, call_next):
    """Rejects API calls that lack the per-launch secret the desktop shell hands us.

    Without it any web page (or local process) could drive the loopback API.
    The token is read per request so tests can set it; unset means open (dev).
    """
    token = os.environ.get("VOICECLONE_API_TOKEN", "")
    if (
        token
        and request.method != "OPTIONS"
        and request.url.path.startswith("/api/")
        and request.url.path not in _OPEN_PATHS
    ):
        supplied = request.headers.get(TOKEN_HEADER) or request.query_params.get("token", "")
        if not secrets.compare_digest(supplied, token):
            return JSONResponse({"detail": "Missing or invalid API token"}, status_code=401)
    return await call_next(request)


@app.exception_handler(RequestValidationError)
async def hide_rejected_input(_: Request, exc: RequestValidationError) -> JSONResponse:
    errors = [{key: value for key, value in error.items() if key not in {"input", "ctx", "url"}} for error in exc.errors()]
    return JSONResponse({"detail": errors}, status_code=422)


app.include_router(api_router)


def main() -> None:
    import uvicorn

    setup_logging(config_manager.config.log_level)
    port = int(os.environ.get("VOICECLONE_API_PORT", str(DEFAULT_PORT)))
    logger.info("Starting VoiceClone API on http://127.0.0.1:%d", port)
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")


if __name__ == "__main__":
    main()
