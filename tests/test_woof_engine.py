import numpy as np

from app.engines.base import SynthesisParameters
from app.engines.woof_engine import WoofEngine


class FakeWoof:
    temp = 0.0

    def __call__(self, text, seed=None):
        self.seen = (text, seed, self.temp)
        return np.zeros(240, dtype=np.float64)


def test_synthesis_passes_voice_temperature_and_seed(monkeypatch):
    engine = WoofEngine()
    fake = FakeWoof()
    asked = []
    monkeypatch.setattr(engine, "_voice", lambda voice: asked.append(voice) or fake)

    audio, rate = engine.clone_and_synthesize("Hi", "", SynthesisParameters(temperature=0.7, seed=5, extra={"voice": "mira"}))

    assert asked == ["mira"] and fake.seen == ("Hi", 5, 0.7)
    assert rate == 24000 and audio.dtype == np.float32


def test_unknown_voice_is_rejected():
    try:
        WoofEngine().clone_and_synthesize("Hi", "", SynthesisParameters(extra={"voice": "rex"}))
    except ValueError as exc:
        assert "rex" in str(exc)
    else:
        raise AssertionError("expected ValueError")
