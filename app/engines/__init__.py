"""
Pluggable speech synthesis and cloning engines interface and implementations.
"""

from app.engines.base import EngineLicense, SynthesisParameters, TTSEngine
from app.engines.chatterbox_engine import ChatterboxEngine
from app.engines.f5_engine import F5Engine
from app.engines.registry import EngineRegistry, engine_registry
from app.engines.xtts_engine import XTTSEngine

__all__ = [
    "TTSEngine",
    "EngineLicense",
    "SynthesisParameters",
    "ChatterboxEngine",
    "XTTSEngine",
    "F5Engine",
    "EngineRegistry",
    "engine_registry",
]

