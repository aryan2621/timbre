"""
Engine registry for discovery, listing, and lifecycle management of TTS engines.
"""

from __future__ import annotations

import threading

from app.core.logging_setup import get_logger
from app.engines.base import Engine, SoundEngine

logger = get_logger("registry")


class EngineRegistry:
    """Thread-safe registry of all pluggable TTS engines."""

    def __init__(self) -> None:
        self._engines: dict[str, Engine] = {}
        self._lock = threading.Lock()
        self._register_default_engines()

    def _register_default_engines(self) -> None:
        """Instantiates and registers standard engines."""
        from app.engines.chatterbox_engine import ChatterboxEngine

        from app.engines.pocket_tts_engine import PocketTTSEngine

        self.register(ChatterboxEngine())
        self.register(PocketTTSEngine())

    def register(self, engine: Engine) -> None:
        """Registers a new TTS engine instance."""
        with self._lock:
            self._engines[engine.name] = engine
            logger.info("Registered TTS engine: %s (%s)", engine.name, engine.license_info.name)

    def get_engine(self, name: str) -> Engine | None:
        """Retrieves an engine by exact name."""
        with self._lock:
            return self._engines.get(name)

    def list_engine_names(self) -> list[str]:
        """Returns the list of names of all registered engines."""
        with self._lock:
            return list(self._engines.keys())

    def get_all_engines(self) -> list[Engine]:
        """Returns all registered engine instances."""
        with self._lock:
            return list(self._engines.values())

    def preload(self) -> None:
        """Loads every engine whose weights are already on disk, so the first job starts at once."""
        for engine in self.get_all_engines():
            try:
                if engine.can_preload() and not engine.is_loaded():
                    with engine.lock:
                        engine.load_model()
                    logger.info("Preloaded engine: %s", engine.name)
            except Exception:  # noqa: BLE001 - a failed warm-up must never stop the server
                logger.warning("Preload failed for %s", engine.name, exc_info=True)

    def unload_all(self) -> None:
        """Unloads all engines currently loaded into device memory."""
        with self._lock:
            for engine in self._engines.values():
                with engine.lock:  # waits for any in-flight synthesis chunk
                    if engine.is_loaded():
                        engine.unload_model()


class SoundEngineRegistry(EngineRegistry):
    def _register_default_engines(self) -> None:
        from app.engines.ace_step_engine import AceStepEngine
        from app.engines.audioldm_engine import AudioLdmEngine
        from app.engines.musicgen_engine import MusicGenEngine
        from app.engines.stable_audio_engine import StableAudioEngine

        self.register(StableAudioEngine())
        self.register(AceStepEngine())
        self.register(AudioLdmEngine())
        self.register(MusicGenEngine())

    def get_engine(self, name: str) -> SoundEngine | None:
        engine = super().get_engine(name)
        return engine if isinstance(engine, SoundEngine) else None


engine_registry = EngineRegistry()
sound_registry = SoundEngineRegistry()

