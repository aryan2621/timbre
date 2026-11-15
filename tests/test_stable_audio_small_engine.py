import io
import json

import numpy as np
import pytest
import soundfile as sf

from app.engines import stable_audio_small_engine as module
from app.engines.base import SoundParameters
from app.engines.stable_audio_small_engine import StableAudioSmallEngine


class FakeServer:
    url = "http://fake"

    def __init__(self, running=True):
        self.running = running
        self.requests = []

    def is_running(self):
        return self.running

    def read(self, request):
        self.requests.append((request.full_url, json.loads(request.data)))
        buffer = io.BytesIO()
        sf.write(buffer, np.zeros((441, 2), dtype=np.float32), 44100, format="WAV", subtype="FLOAT")
        return buffer.getvalue()


def test_generate_sends_request_and_decodes_stereo(monkeypatch):
    server = FakeServer()
    monkeypatch.setattr(module, "SERVER", server)
    steps = []
    params = SoundParameters(duration_seconds=30.0, steps=8, guidance=1.0, seed=7)
    audio, rate = StableAudioSmallEngine().generate("door slam", params, lambda a, b: steps.append((a, b)))
    url, body = server.requests[0]
    assert url == "http://fake/generate"
    assert body == {"prompt": "door slam", "seconds": 11.0, "steps": 8, "cfg_scale": 1.0, "seed": 7}
    assert audio.shape == (441, 2) and audio.dtype == np.float32 and rate == 44100
    assert steps == [(8, 8)]


def test_generate_requires_running_server(monkeypatch):
    monkeypatch.setattr(module, "SERVER", FakeServer(running=False))
    with pytest.raises(RuntimeError):
        StableAudioSmallEngine().generate("x", SoundParameters(duration_seconds=1.0, steps=8, guidance=1.0))
