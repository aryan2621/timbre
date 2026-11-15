import hashlib
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from app.api.downloads import DownloadJob, DownloadManager
from app.data import model_catalog
from app.data.models import ModelFile, ModelMetadata
from app.runtimes.native import find_native


class TestEngineCatalog(unittest.TestCase):
    def test_host_engines_are_executable_catalog_entries(self):
        engines = [m for m in model_catalog.CATALOG_MODELS if m.category == "engine"]
        if model_catalog._host_triple() == "aarch64-apple-darwin":
            self.assertEqual({m.id for m in engines}, {"engine-mlx-audio", "engine-sfx"})
        for engine in engines:
            self.assertTrue(engine.executable)
            self.assertEqual(engine.total_bytes, engine.files[0].size)
            self.assertEqual(len(engine.files[0].sha256), 64)

    def test_models_point_at_an_existing_engine(self):
        ids = {m.id for m in model_catalog.CATALOG_MODELS}
        needing = [m for m in model_catalog.CATALOG_MODELS if m.requires_engine]
        for model in needing:
            self.assertIn(model.requires_engine, ids)
        if model_catalog._host_triple() == "aarch64-apple-darwin":
            self.assertIn("kokoro-82m", {m.id for m in needing})


class TestEngineDownload(unittest.TestCase):
    def test_download_marks_engine_executable_and_find_native_sees_it(self):
        body = b"#!/bin/sh\nexit 0\n"

        class Resp:
            status = 200
            headers = {"Content-Length": str(len(body))}
            sent = False

            def __enter__(self):
                return self

            def __exit__(self, *_):
                return False

            def read(self, _n):
                data, self.sent = (b"" if self.sent else body), True
                return data

        file = ModelFile("fake-server", "http://x/fake-server", len(body), hashlib.sha256(body).hexdigest())
        model = ModelMetadata(
            id="e", name="E", version="1", license_name="", commercial_allowed=True, license_notice="",
            total_bytes=len(body), local_dir="engines/fake-server", files=[file], executable=True,
        )
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            job = DownloadJob(id="j", model_id="e", model_name="E")
            (root / "engines" / "fake-server").mkdir(parents=True)
            with mock.patch("urllib.request.urlopen", return_value=Resp()):
                DownloadManager()._run(job, model, root)
            self.assertEqual(job.state, "done")
            path = root / "engines" / "fake-server" / "fake-server"
            self.assertTrue(os.access(path, os.X_OK))
            with mock.patch("app.core.config.config_manager.get_models_directory", return_value=root):
                self.assertEqual(find_native("fake-server"), path)


if __name__ == "__main__":
    unittest.main()
