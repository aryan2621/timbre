"""
Regression tests for the safety fixes from the whole-app audit.
"""

import hashlib
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from app.api.downloads import DownloadJob, DownloadManager
import app.data.database as db_mod
import app.data.history_repo  # noqa: F401
from app.data.models import HistoryEntry, ModelFile, ModelMetadata
from tests.test_api_batch import _BatchApiTestCase


def _batch_payload(engine, items):
    return {
        "voice_id": 1,
        "engine_name": engine.name,
        "items": items,
        "params": {"language": "en", "seed": 7},
    }


class TestBatchFilenames(_BatchApiTestCase):
    def _run(self, items):
        response = self.client.post(
            "/api/batch",
            json={**_batch_payload(self.engine, items), "output_dir": str(self.output_dir)},
        )
        self.assertEqual(response.status_code, 200, response.text)
        return self.wait_for_batch(response.json()["id"])

    def test_path_in_filename_stays_inside_output_dir(self):
        status = self._run(
            [
                {"text": "One.", "filename": "../../evil.wav"},
                {"text": "Two.", "filename": "/tmp/voiceclone-abs.wav"},
            ]
        )
        self.assertEqual(status["state"], "done")
        self.assertEqual(sorted(i["filename"] for i in status["items"]), ["evil.wav", "voiceclone-abs.wav"])
        self.assertTrue((self.output_dir / "evil.wav").exists())
        self.assertFalse((self.output_dir.parent.parent / "evil.wav").exists())
        self.assertFalse(Path("/tmp/voiceclone-abs.wav").exists())

    def test_duplicate_filenames_do_not_overwrite(self):
        status = self._run([{"text": "One.", "filename": "a.wav"}, {"text": "Two.", "filename": "a.wav"}])
        self.assertEqual([i["filename"] for i in status["items"]], ["a.wav", "a_2.wav"])
        self.assertTrue((self.output_dir / "a.wav").exists())
        self.assertTrue((self.output_dir / "a_2.wav").exists())

    def test_existing_file_on_disk_is_not_overwritten(self):
        self.output_dir.mkdir(parents=True, exist_ok=True)
        (self.output_dir / "keep.wav").write_bytes(b"MINE")
        self._run([{"text": "One.", "filename": "keep.wav"}])
        self.assertEqual((self.output_dir / "keep.wav").read_bytes(), b"MINE")
        self.assertTrue((self.output_dir / "keep_2.wav").exists())


class TestOneRenderAtATime(_BatchApiTestCase):
    def test_second_render_gets_409_while_busy(self):
        self.engine.delay = 0.3
        first = self.client.post(
            "/api/batch",
            json={**_batch_payload(self.engine, [{"text": "Slow one."}]), "output_dir": str(self.output_dir)},
        )
        self.assertEqual(first.status_code, 200)
        second = self.client.post(
            "/api/synthesize",
            json={"voice_id": 1, "engine_name": self.engine.name, "text": "Another."},
        )
        self.assertEqual(second.status_code, 409)
        self.wait_for_batch(first.json()["id"])


class TestApiToken(_BatchApiTestCase):
    def test_token_is_required_except_for_health(self):
        with mock.patch.dict("os.environ", {"VOICECLONE_API_TOKEN": "s3cret"}):
            self.assertEqual(self.client.get("/api/engines").status_code, 401)
            self.assertEqual(
                self.client.get("/api/engines", headers={"X-VoiceClone-Token": "wrong"}).status_code, 401
            )
            self.assertEqual(
                self.client.get("/api/engines", headers={"X-VoiceClone-Token": "s3cret"}).status_code, 200
            )
            self.assertEqual(self.client.get("/api/engines?token=s3cret").status_code, 200)
            self.assertEqual(self.client.get("/api/health").status_code, 200)

    def test_unknown_origin_is_not_allowed(self):
        response = self.client.options(
            "/api/voices",
            headers={"Origin": "null", "Access-Control-Request-Method": "GET"},
        )
        self.assertNotIn("access-control-allow-origin", response.headers)


class TestHistoryDeleteScope(unittest.TestCase):
    def test_only_files_in_history_dir_are_deleted(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            owned_dir, user_dir = root / "history", root / "mine"
            owned_dir.mkdir()
            user_dir.mkdir()
            owned, mine = owned_dir / "a.wav", user_dir / "b.wav"
            owned.write_bytes(b"x")
            mine.write_bytes(b"y")

            history_mod = sys.modules["app.data.history_repo"]
            original = db_mod.db_manager
            db_mod.db_manager = db_mod.DatabaseManager(root / "t.db")
            try:
                with mock.patch.object(history_mod, "paths", SimpleNamespace(history_dir=owned_dir)):
                    repo = history_mod.HistoryRepository()
                    entries = [
                        repo.add_entry(
                            HistoryEntry(voice_id=None, voice_name="v", engine_name="e", prompt_text="t",
                                         audio_path=str(p), duration_seconds=1.0, sample_rate=24000)
                        )
                        for p in (owned, mine)
                    ]
                    repo.delete_entry(entries[0].id)
                    self.assertFalse(owned.exists())
                    repo.clear_all()
                    self.assertTrue(mine.exists())
            finally:
                db_mod.db_manager = original


class _Resp:
    def __init__(self, status, body, claimed_length=None):
        self.status, self._body = status, body
        self.headers = {"Content-Length": str(claimed_length if claimed_length is not None else len(body))}
        self._sent = False

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self, n):
        if self._sent:
            return b""
        self._sent = True
        return self._body


class TestDownload(unittest.TestCase):
    def _run(self, directory: Path, body: bytes, response=None, error=None, part: bytes | None = None):
        file = ModelFile("m.bin", "http://x/m.bin", len(body), hashlib.sha256(body).hexdigest())
        model = ModelMetadata(
            id="m", name="M", version="1", license_name="", commercial_allowed=True, license_notice="",
            download_url=file.url, expected_sha256="", total_bytes=len(body), local_dir="m", files=[file],
        )
        target = directory / "m"
        target.mkdir()
        if part is not None:
            (target / "m.bin.part").write_bytes(part)
        job = DownloadJob(id="j", model_id="m", model_name="M")
        with mock.patch("urllib.request.urlopen", return_value=response, side_effect=error):
            DownloadManager()._run(job, model, directory)
        return job, target

    def test_server_ignoring_range_does_not_corrupt_file(self):
        with tempfile.TemporaryDirectory() as d:
            job, target = self._run(Path(d), b"FULLBODY", response=_Resp(200, b"FULLBODY"), part=b"STALE")
            self.assertEqual(job.state, "done")
            self.assertEqual((target / "m.bin").read_bytes(), b"FULLBODY")

    def test_416_with_complete_part_file_finishes(self):
        with tempfile.TemporaryDirectory() as d:
            err = urllib.error.HTTPError("http://x", 416, "range", {}, None)
            job, target = self._run(Path(d), b"COMPLETE", error=err, part=b"COMPLETE")
            self.assertEqual(job.state, "done")
            self.assertEqual((target / "m.bin").read_bytes(), b"COMPLETE")

    def test_truncated_download_fails_and_keeps_part_file(self):
        with tempfile.TemporaryDirectory() as d:
            job, target = self._run(Path(d), b"FULLBODY", response=_Resp(200, b"FULL", claimed_length=8))
            self.assertEqual(job.state, "failed")
            self.assertFalse((target / "m.bin").exists())
            self.assertEqual((target / "m.bin.part").read_bytes(), b"FULL")

    def test_checksum_mismatch_deletes_file(self):
        with tempfile.TemporaryDirectory() as d:
            job, target = self._run(Path(d), b"GOODBODY", response=_Resp(200, b"EVILBODY"))
            self.assertEqual(job.state, "failed")
            self.assertFalse((target / "m.bin").exists())



class TestLiveChunksAndPostprocess(_BatchApiTestCase):
    SENTENCE = "This is a fairly long sentence that is used to force several chunks in one render. "

    def test_chunks_are_served_and_postprocess_is_applied(self):
        import io

        import soundfile as sf

        calls = []

        def halve(audio, sample_rate, params):
            calls.append(threading.current_thread().name)
            return audio * 0.5

        self.engine.postprocess_chunk = halve
        response = self.client.post(
            "/api/synthesize",
            json={
                "voice_id": 1,
                "engine_name": self.engine.name,
                "text": self.SENTENCE * 6,
                "sentence_pause_ms": 100,
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        job_id = response.json()["id"]

        deadline = time.time() + 30
        while time.time() < deadline:
            job = self.client.get(f"/api/jobs/{job_id}").json()
            if job["state"] in {"done", "failed", "cancelled"}:
                break
            time.sleep(0.05)
        self.assertEqual(job["state"], "done", job)
        self.assertGreater(job["total_chunks"], 1)
        self.assertEqual(job["chunks_ready"], job["total_chunks"])
        self.assertTrue(all(name.startswith("postprocess") for name in calls))

        # Every chunk is a playable WAV, and together they are as long as the final file.
        total = 0.0
        for index in range(job["chunks_ready"]):
            chunk = self.client.get(f"/api/jobs/{job_id}/chunks/{index}")
            self.assertEqual(chunk.status_code, 200)
            data, rate = sf.read(io.BytesIO(chunk.content))
            self.assertLess(abs(data).max(), 0.2)  # halved from 0.3
            total += len(data) / rate
        self.assertAlmostEqual(total, job["duration_seconds"], delta=0.01)
        self.assertEqual(self.client.get(f"/api/jobs/{job_id}/chunks/999").status_code, 404)


if __name__ == "__main__":
    unittest.main()
