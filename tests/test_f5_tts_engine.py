import numpy as np
import pytest

from app.engines import f5_tts_engine as module
from app.engines.base import SynthesisParameters
from app.engines.f5_tts_engine import F5TTSEngine


class FakeF5:
    def infer(self, **kwargs):
        self.kwargs = kwargs
        return np.zeros(240, dtype=np.float64), 24000, None


def _engine(monkeypatch, transcript: str) -> tuple[F5TTSEngine, FakeF5]:
    engine = F5TTSEngine()
    engine._model = FakeF5()
    monkeypatch.setattr(module, "reference_transcript", lambda clip: transcript)
    return engine, engine._model


def test_clone_passes_transcript_controls_and_seed(monkeypatch):
    engine, fake = _engine(monkeypatch, "Some call me nature.")
    params = SynthesisParameters(speed=1.1, seed=7, extra={"nfe_step": 16, "cfg_strength": 3.0})

    audio, rate = engine.clone_and_synthesize("Hello", "/clip.wav", params)

    assert (rate, audio.dtype) == (24000, np.float32)
    assert fake.kwargs["ref_file"] == "/clip.wav" and fake.kwargs["ref_text"] == "Some call me nature."
    assert (fake.kwargs["nfe_step"], fake.kwargs["cfg_strength"], fake.kwargs["speed"], fake.kwargs["seed"]) == (16, 3.0, 1.1, 7)


def test_random_seed_is_not_forwarded(monkeypatch):
    engine, fake = _engine(monkeypatch, "Hi.")
    engine.clone_and_synthesize("Hello", "/clip.wav", SynthesisParameters(seed=-1))
    assert fake.kwargs["seed"] is None


def test_missing_transcript_is_an_error_not_a_whisper_download(monkeypatch):
    engine, _ = _engine(monkeypatch, "")
    with pytest.raises(RuntimeError, match="transcript"):
        engine.clone_and_synthesize("Hello", "/clip.wav", SynthesisParameters())
