"""
Engine registry for discovery, listing, and lifecycle management of TTS engines.
"""

from __future__ import annotations

import threading

from app.core.logging_setup import get_logger
from app.engines.base import TTSEngine

logger = get_logger("registry")


class EngineRegistry:
    """Thread-safe registry of all pluggable TTS engines."""

    def __init__(self) -> None:
        self._engines: dict[str, TTSEngine] = {}
        self._lock = threading.Lock()
        self._register_default_engines()

    def _register_default_engines(self) -> None:
        """Instantiates and registers standard engines."""
        from app.engines.chatterbox_engine import ChatterboxEngine
        from app.engines.f5_engine import F5Engine
        from app.engines.xtts_engine import XTTSEngine

        self.register(ChatterboxEngine())
        self.register(XTTSEngine())
        self.register(F5Engine())

    def register(self, engine: TTSEngine) -> None:
        """Registers a new TTS engine instance."""
        with self._lock:
            self._engines[engine.name] = engine
            logger.info("Registered TTS engine: %s (%s)", engine.name, engine.license_info.name)

    def get_engine(self, name: str) -> TTSEngine | None:
        """Retrieves an engine by exact name."""
        with self._lock:
            return self._engines.get(name)

    def list_engine_names(self) -> list[str]:
        """Returns the list of names of all registered engines."""
        with self._lock:
            return list(self._engines.keys())

    def get_all_engines(self) -> list[TTSEngine]:
        """Returns all registered engine instances."""
        with self._lock:
            return list(self._engines.values())

    def unload_all(self) -> None:
        """Unloads all engines currently loaded into device memory."""
        with self._lock:
            for engine in self._engines.values():
                with engine.lock:  # waits for any in-flight synthesis chunk
                    if engine.is_loaded():
                        engine.unload_model()


# Global singleton instance
engine_registry = EngineRegistry()

