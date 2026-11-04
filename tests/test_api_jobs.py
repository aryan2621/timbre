"""
End-to-end tests for the job based synthesis API (no streaming transport).
"""

from __future__ import annotations

import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import numpy as np
from fastapi.testclient import TestClient

from app.api import server as server_mod
from app.engines.base import EngineLicense, SynthesisParameters, TTSEngine


class _FakeEngine(TTSEngine):
    """Engine stub that renders a constant tone for every chunk."""

    def __init__(self, tone_length: int = 2400, delay: float = 0.0) -> None:
        self.tone_length = tone_length
        self.delay = delay
        self.chunks_rendered: list[str] = []

    @property
    def name(self) -> str:
        return "Fake Stream Engine"

    @property
    def license_info(self) -> EngineLicense:
        return EngineLicense(
            name="MIT",
            url="https://example.invalid",
            commercial_permitted=True,
            notice="Test only.",
        )

    @property
    def supported_languages(self) -> list[str]:
        return ["en"]

    @property
    def requires_gpu_recommended(self) -> bool:
        return False

    @property
    def native_sample_rate(self) -> int:
        return 24000

    def is_available(self) -> bool:
        return True

    def is_loaded(self) -> bool:
        return True

    def load_model(self, progress_callback=None) -> bool:
        return True

    def unload_model(self) -> None:
        return None

    def clone_and_synthesize(self, text, reference_audio_path, params):
        if self.delay:
            time.sleep(self.delay)
        self.chunks_rendered.append(text)
        return np.full(self.tone_length, 0.4, dtype=np.float32), self.native_sample_rate

    def get_default_params(self) -> SynthesisParameters:
        return SynthesisParameters()


class _JobApiTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = _FakeEngine()
        self.profile = SimpleNamespace(
            id=1,
            name="Test Voice",
            primary_audio_path="unused.wav",
        )
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

        patches = [
            mock.patch.object(server_mod.engine_registry, "get_engine", return_value=self.engine),
            mock.patch.object(server_mod.voice_repo, "get_profile_by_id", return_value=self.profile),
            mock.patch.object(
                server_mod,
                "paths",
                SimpleNamespace(
                    history_dir=Path(self.tmp.name),
                    data_dir=Path(self.tmp.name),
                    voices_dir=Path(self.tmp.name),
                ),
            ),
            mock.patch.object(
                server_mod.history_repo,
                "add_entry",
                return_value=SimpleNamespace(id=4242),
            ),
        ]
        for patcher in patches:
            patcher.start()
            self.addCleanup(patcher.stop)

        self.client = TestClient(server_mod.app)

    def wait_for_job(self, job_id: str, states=("done", "failed", "cancelled")) -> dict:
        deadline = time.time() + 30
        payload: dict = {}
        while time.time() < deadline:
            payload = self.client.get(f"/api/jobs/{job_id}").json()
            if payload.get("state") in states:
                return payload
            time.sleep(0.05)
        self.fail(f"job {job_id} never reached {states}: {payload}")


class TestJobFlow(_JobApiTestCase):
    def test_synthesize_creates_a_job_that_finishes(self):
        text = " ".join(
            f"This is sentence number {index} with a reasonable amount of words."
            for index in range(1, 4)
        )
        response = self.client.post(
            "/api/synthesize",
            json={
                "voice_id": 1,
                "engine_name": self.engine.name,
                "text": text,
                "params": {"language": "en"},
                "sentence_pause_ms": 250,
            },
        )
        self.assertEqual(response.status_code, 200)
        created = response.json()
        self.assertIn(created["state"], {"queued", "running"})
        self.assertGreaterEqual(created["total_chunks"], 1)

        status = self.wait_for_job(created["id"])
        self.assertEqual(status["state"], "done")
        self.assertEqual(status["progress"], 100.0)
        self.assertIn("/api/history/4242/audio", status["audio_url"])
        self.assertGreater(status["duration_seconds"], 0)
        # The waveform peaks are part of the job status, so the UI can draw
        # the render without downloading the file first.
        self.assertTrue(status["peaks"])

        # The render was written to the history directory.
        written = list(Path(self.tmp.name).glob("*.wav"))
        self.assertEqual(len(written), 1)

    def test_job_can_be_cancelled(self):
        self.engine.delay = 0.4
        text = " ".join(
            f"This is sentence number {index} with a reasonable amount of words."
            for index in range(1, 6)
        )
        created = self.client.post(
            "/api/synthesize",
            json={
                "voice_id": 1,
                "engine_name": self.engine.name,
                "text": text,
                "params": {"language": "en"},
            },
        ).json()

        cancelled = self.client.post(f"/api/jobs/{created['id']}/cancel").json()
        self.assertIn(cancelled["state"], {"queued", "running", "cancelled"})

        status = self.wait_for_job(created["id"])
        self.assertEqual(status["state"], "cancelled")
        # The render stopped early, so not every chunk was rendered.
        self.assertLess(len(self.engine.chunks_rendered), 5)

    def test_synthesize_rejects_unknown_voice(self):
        with mock.patch.object(server_mod.voice_repo, "get_profile_by_id", return_value=None):
            response = self.client.post(
                "/api/synthesize",
                json={
                    "voice_id": 99,
                    "engine_name": self.engine.name,
                    "text": "Hello there.",
                },
            )
        self.assertEqual(response.status_code, 404)

    def test_synthesize_rejects_empty_text(self):
        response = self.client.post(
            "/api/synthesize",
            json={
                "voice_id": 1,
                "engine_name": self.engine.name,
                "text": "   ",
            },
        )
        self.assertEqual(response.status_code, 400)


if __name__ == "__main__":
    unittest.main()
