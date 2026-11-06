"""
Unit tests for TTSEngine Registry and adapter interfaces.
"""

import unittest

try:
    import numpy as np
except ImportError:
    np = None

from app.engines.base import EngineLicense, SynthesisParameters, TTSEngine
from app.engines.registry import EngineRegistry


class MockCustomEngine(TTSEngine):

    def __init__(self):
        self._loaded = False

    @property
    def name(self) -> str:
        return "Mock Custom Engine"

    @property
    def license_info(self) -> EngineLicense:
        return EngineLicense(
            name="Apache 2.0",
            url="https://apache.org",
            commercial_permitted=True,
            notice="Mock test notice",
        )

    @property
    def supported_languages(self) -> list[str]:
        return ["en", "de"]

    @property
    def requires_gpu_recommended(self) -> bool:
        return False

    @property
    def native_sample_rate(self) -> int:
        return 22050

    def is_available(self) -> bool:
        return True

    def is_loaded(self) -> bool:
        return self._loaded

    def load_model(self, progress_callback=None) -> bool:
        self._loaded = True
        return True

    def unload_model(self) -> None:
        self._loaded = False

    def clone_and_synthesize(self, text, reference_audio_path, params):
        return np.zeros(22050, dtype=np.float32), 22050

    def get_default_params(self) -> SynthesisParameters:
        return SynthesisParameters()


class TestEngineRegistry(unittest.TestCase):

    def test_default_engines_registered(self):
        reg = EngineRegistry()
        names = reg.list_engine_names()
        self.assertIn("Chatterbox TTS", names)

    def test_custom_engine_registration_and_lifecycle(self):
        reg = EngineRegistry()
        mock = MockCustomEngine()
        reg.register(mock)

        engine = reg.get_engine("Mock Custom Engine")
        self.assertIsNotNone(engine)
        self.assertEqual(engine.license_info.commercial_permitted, True)

        self.assertFalse(engine.is_loaded())
        engine.load_model()
        self.assertTrue(engine.is_loaded())

        reg.unload_all()
        self.assertFalse(engine.is_loaded())


if __name__ == "__main__":
    unittest.main()
