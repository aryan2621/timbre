"""
FastAPI sidecar for VoiceClone Studio.

The Tauri/React frontend talks to this service over loopback HTTP. This module
is the composition root: it wires the FastAPI app, middleware, lifespan and
routers. Business logic lives in ``app.services`` and HTTP contracts live in
``app.api.schemas`` / ``app.api.routes``.
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from app.api.routes import api_router
from app.core.config import AppConfig, config_manager
from app.core.logging_setup import get_logger, setup_logging
from app.engines.registry import engine_registry
from app.services.voice_service import seed_demo_voice

logger = get_logger("api")

API_VERSION = "0.1.0"
DEFAULT_PORT = 8756


# Re-exported for backwards compatibility with existing imports/tests.
from app.core.paths import paths  # noqa: E402,F401
from app.data.history_repo import history_repo  # noqa: E402,F401
from app.data.voice_repo import voice_repo  # noqa: E402,F401

app = FastAPI(title="VoiceClone Studio API", version=API_VERSION)

app.add_middleware(GZipMiddleware, minimum_size=1024)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:1420",
        "http://127.0.0.1:1420",
        "tauri://localhost",
        "http://tauri.localhost",
        "https://tauri.localhost",
        "null",
    ],
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(api_router)


@asynccontextmanager
async def lifespan(_: FastAPI):
    setup_logging(config_manager.config.log_level)
    logger.info("VoiceClone API %s starting on loopback.", API_VERSION)
    try:
        seed_demo_voice()
    except Exception:  # noqa: BLE001 - never block startup on demo seeding
        logger.exception("Could not seed the demo voice")
    try:
        yield
    finally:
        try:
            engine_registry.unload_all()
        except Exception:  # pragma: no cover
            logger.debug("Engine unload during shutdown failed", exc_info=True)
        logger.info("VoiceClone API stopped.")


def main() -> None:
    import uvicorn

    setup_logging(config_manager.config.log_level)
    port = int(os.environ.get("VOICECLONE_API_PORT", str(DEFAULT_PORT)))
    logger.info("Starting VoiceClone API on http://127.0.0.1:%d", port)
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")


if __name__ == "__main__":
    main()
