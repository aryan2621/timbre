import io
import json

import numpy as np
import soundfile as sf

from app.engines import mlx_audio_engine as module
from app.engines.base import SynthesisParameters
from app.engines.mlx_audio_engine import SPECS, MlxAudioEngine


class FakeServer:
    url = "http://fake"

    def __init__(self, audio: bytes):
        self.audio = audio
        self.requests = []

    def is_running(self):
        return True

    def read(self, request):
        self.requests.append((request.full_url, json.loads(request.data)))
        return self.audio


def _wav(samples: np.ndarray, rate: int = 24000) -> bytes:
    buffer = io.BytesIO()
    sf.write(buffer, samples, rate, format="WAV")
    return buffer.getvalue()


def test_kokoro_sends_preset_voice_and_decodes_wav(monkeypatch):
    server = FakeServer(_wav(np.zeros(2400, dtype=np.float32)))
    monkeypatch.setattr(module, "SERVER", server)
    engine = MlxAudioEngine(SPECS[0])
    params = SynthesisParameters(speed=1.2, extra={"voice": "bf_emma"})

    audio, rate = engine.clone_and_synthesize("Hello", "/ignored.wav", params)

    url, body = server.requests[0]
    assert url.endswith("/v1/audio/speech")
    assert body["voice"] == "bf_emma" and body["lang_code"] == "b" and body["speed"] == 1.2
    assert "ref_audio" not in body and body["model"].endswith("kokoro-82m")
    assert rate == 24000 and audio.dtype == np.float32 and audio.shape == (2400,)


def test_empty_response_is_an_error(monkeypatch):
    monkeypatch.setattr(module, "SERVER", FakeServer(b""))
    try:
        MlxAudioEngine(SPECS[0]).clone_and_synthesize("Hi", "", SynthesisParameters())
    except RuntimeError as exc:
        assert "no audio" in str(exc)
    else:
        raise AssertionError("expected RuntimeError")


def test_qwen_clones_with_cached_transcript(monkeypatch, tmp_path):
    server = FakeServer(_wav(np.zeros(2400, dtype=np.float32)))
    monkeypatch.setattr(module, "SERVER", server)
    clip = tmp_path / "ref.wav"
    clip.write_bytes(b"x")
    (tmp_path / "ref.wav.txt").write_text("the transcript\n")
    spec = next(s for s in SPECS if s.model_id == "qwen3-tts-0.6b")

    MlxAudioEngine(spec).clone_and_synthesize("Hello", clip, SynthesisParameters(language="en"))

    body = server.requests[0][1]
    assert body["ref_audio"] == str(clip) and body["ref_text"] == "the transcript" and body["lang_code"] == "en"
    assert "voice" not in body


def test_missing_transcript_falls_back_to_empty(tmp_path):
    clip = tmp_path / "ref.wav"
    clip.write_bytes(b"x")
    assert module.reference_transcript(clip) == ""


def test_zonos_uses_clip_by_default_and_preset_when_chosen(monkeypatch):
    server = FakeServer(_wav(np.zeros(2400, dtype=np.float32), 44100))
    monkeypatch.setattr(module, "SERVER", server)
    engine = MlxAudioEngine(next(s for s in SPECS if s.model_id == "zonos3-mini"))

    engine.clone_and_synthesize("Hi", "/clip.wav", SynthesisParameters())
    engine.clone_and_synthesize("Hi", "/clip.wav", SynthesisParameters(extra={"voice": "jett"}))

    clip, preset = server.requests[0][1], server.requests[1][1]
    assert clip["ref_audio"] == "/clip.wav" and "voice" not in clip
    assert preset["voice"] == "jett" and "ref_audio" not in preset and "lang_code" not in preset
