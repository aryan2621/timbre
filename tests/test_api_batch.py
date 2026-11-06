"""End-to-end tests for the batch rendering endpoint."""

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
from app.services import synthesis_service


class _FakeEngine(TTSEngine):
    """Engine stub that renders a short constant tone for every chunk."""

    def __init__(self, tone_length: int = 1200, delay: float = 0.0) -> None:
        self.tone_length = tone_length
        self.delay = delay
        self.rendered: list[str] = []

    @property
    def name(self) -> str:
        return "Fake Batch Engine"

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
        self.rendered.append(text)
        return np.full(self.tone_length, 0.3, dtype=np.float32), self.native_sample_rate

    def get_default_params(self) -> SynthesisParameters:
        return SynthesisParameters()


class _BatchApiTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = _FakeEngine()
        self.profile = SimpleNamespace(id=1, name="Test Voice", primary_audio_path="unused.wav")
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.output_dir = Path(self.tmp.name) / "out"
        # A tiny in-memory stand-in for the history repository.
        self.history: dict[int, object] = {}
        self.history_id = 0

        def add_entry(entry):
            self.history_id += 1
            self.history[self.history_id] = entry
            return SimpleNamespace(id=self.history_id)

        def get_entry_by_id(entry_id):
            return self.history.get(entry_id)

        patches = [
            mock.patch.object(server_mod.engine_registry, "get_engine", return_value=self.engine),
            mock.patch.object(server_mod.voice_repo, "get_profile_by_id", return_value=self.profile),
            mock.patch.object(
                synthesis_service,
                "paths",
                SimpleNamespace(
                    history_dir=Path(self.tmp.name),
                    data_dir=Path(self.tmp.name),
                    voices_dir=Path(self.tmp.name),
                ),
            ),
            mock.patch.object(server_mod.history_repo, "add_entry", side_effect=add_entry),
            mock.patch.object(
                server_mod.history_repo, "get_entry_by_id", side_effect=get_entry_by_id
            ),
        ]
        for patcher in patches:
            patcher.start()
            self.addCleanup(patcher.stop)

        self.client = TestClient(server_mod.app)

    def wait_for_batch(self, job_id: str) -> dict:
        deadline = time.time() + 30
        payload: dict = {}
        while time.time() < deadline:
            payload = self.client.get(f"/api/batch/{job_id}").json()
            if payload.get("state") in {"done", "failed", "cancelled"}:
                return payload
            time.sleep(0.05)
        raise AssertionError(f"batch {job_id} never finished: {payload}")


class TestBatchFlow(_BatchApiTestCase):
    def test_batch_renders_every_line(self):
        response = self.client.post(
            "/api/batch",
            json={
                "voice_id": 1,
                "engine_name": self.engine.name,
                "items": [
                    {"text": "First line of the script.", "filename": "one.wav"},
                    {"text": "Second line of the script.", "filename": "two.wav"},
                    {"text": "   ", "filename": "skipped.wav"},
                ],
                "params": {"language": "en", "seed": 7},
                "sentence_pause_ms": 200,
                "output_dir": str(self.output_dir),
            },
        )
        self.assertEqual(response.status_code, 200)
        created = response.json()
        self.assertEqual(created["total"], 2)

        status = self.wait_for_batch(created["id"])
        self.assertEqual(status["state"], "done")
        self.assertEqual(status["completed"], 2)
        self.assertEqual(status["failed"], 0)
        self.assertEqual(status["progress"], 100.0)

        # Every line got a file and a playable history URL.
        for item in status["items"]:
            self.assertEqual(item["state"], "done")
            self.assertGreater(item["duration_seconds"], 0)
            self.assertIn("/api/history/", item["audio_url"])
            self.assertTrue((self.output_dir / item["filename"]).exists())

        # The audio is served for a finished line.
        audio = self.client.get(status["items"][0]["audio_url"])
        self.assertEqual(audio.status_code, 200)
        self.assertGreater(len(audio.content), 0)

    def test_batch_rejects_an_empty_queue(self):
        response = self.client.post(
            "/api/batch",
            json={
                "voice_id": 1,
                "engine_name": self.engine.name,
                "items": [{"text": "  ", "filename": "empty.wav"}],
            },
        )
        self.assertEqual(response.status_code, 400)

    def test_batch_rejects_an_unknown_voice(self):
        with mock.patch.object(server_mod.voice_repo, "get_profile_by_id", return_value=None):
            response = self.client.post(
                "/api/batch",
                json={
                    "voice_id": 99,
                    "engine_name": self.engine.name,
                    "items": [{"text": "Hello there.", "filename": "hello.wav"}],
                },
            )
        self.assertEqual(response.status_code, 404)

    def test_batch_can_be_cancelled(self):
        self.engine.delay = 0.4
        created = self.client.post(
            "/api/batch",
            json={
                "voice_id": 1,
                "engine_name": self.engine.name,
                "items": [
                    {"text": f"Line number {index} of the batch script.", "filename": f"l{index}.wav"}
                    for index in range(1, 6)
                ],
            },
        ).json()

        cancelled = self.client.post(f"/api/batch/{created['id']}/cancel").json()
        self.assertIn(cancelled["state"], {"queued", "running", "cancelled"})

        status = self.wait_for_batch(created["id"])
        self.assertIn(status["state"], {"cancelled", "done"})
        if status["state"] == "cancelled":
            self.assertLess(len(self.engine.rendered), 5)

    def test_unknown_batch_is_a_404(self):
        response = self.client.get("/api/batch/does-not-exist")
        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
