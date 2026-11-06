"""
Pluggable speech synthesis and cloning engines interface and implementations.
"""

from app.engines.base import EngineLicense, SynthesisParameters, TTSEngine
from app.engines.chatterbox_engine import ChatterboxEngine
from app.engines.registry import EngineRegistry, engine_registry

__all__ = [
    "TTSEngine",
    "EngineLicense",
    "SynthesisParameters",
    "ChatterboxEngine",
    "EngineRegistry",
    "engine_registry",
]

