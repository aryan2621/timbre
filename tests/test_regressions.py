"""
Regression tests for bugs found in the whole-app audit.
"""

import sqlite3
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest import mock

import numpy as np

from app.audio.chunker import TextChunker
from app.data.database import DatabaseManager
from app.data.models import VoiceClip, VoiceProfile
from app.data.voice_repo import VoiceRepository
from app.workers.batch_worker import BatchWorker
from app.workers.download_worker import ModelDownloadWorker
from app.workers.synth_worker import SynthesisWorker


class TestChunkerRegression(unittest.TestCase):
    def test_whitespace_only_part_does_not_duplicate_text(self):
        sentence = "alpha, " + " " * 40 + ", beta"
        joined = " ".join(TextChunker._split_long_sentence(sentence, max_chars=10))
        self.assertEqual(joined.count("alpha"), 1)


class TestStitch(unittest.TestCase):
    def test_all_empty_chunks_return_empty_array(self):
        out = SynthesisWorker._stitch_chunks_with_crossfade([np.zeros(0, dtype=np.float32)] * 2, 24000)
        self.assertEqual(len(out), 0)


class TestBatchParsing(unittest.TestCase):
    def _parse(self, name, content):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / name
            p.write_text(content, encoding="utf-8")
            return BatchWorker.parse_file(p)

    def test_csv_without_header_keeps_first_row(self):
        jobs = self._parse("a.csv", "Hello there,one.wav\nSecond,two.wav\n")
        self.assertEqual([j.text for j in jobs], ["Hello there", "Second"])

    def test_csv_with_header_skips_it(self):
        jobs = self._parse("a.csv", "text,filename\nHello,one.wav\n")
        self.assertEqual([j.text for j in jobs], ["Hello"])

    def test_srt_with_bom_keeps_index_out_of_text(self):
        jobs = self._parse("a.srt", "﻿1\n00:00:00,000 --> 00:00:01,000\nHi there\n")
        self.assertEqual(jobs[0].text, "Hi there")


class TestProfileAtomicity(unittest.TestCase):
    def test_duplicate_name_leaves_no_orphan_and_raises(self):
        import app.data.database as db_mod
        with tempfile.TemporaryDirectory() as d:
            original = db_mod.db_manager
            db_mod.db_manager = DatabaseManager(Path(d) / "t.db")
            try:
                repo = VoiceRepository()
                def mk() -> VoiceProfile:
                    return VoiceProfile(
                        name="Same", language="en", consent_confirmed=True,
                        clips=[VoiceClip(file_path="x.wav", original_filename="x.wav", duration_seconds=1.0, sample_rate=24000)],
                    )
                repo.create_profile(mk())
                with self.assertRaises(sqlite3.IntegrityError):
                    repo.create_profile(mk())
                self.assertEqual(len(repo.list_all_profiles()), 1)
            finally:
                db_mod.db_manager = original


class _FakeResponse:
    def __init__(self, status, body):
        self.status, self._body, self.headers = status, body, {"Content-Length": str(len(body))}
        self._read = False

    def __enter__(self): return self
    def __exit__(self, *a): return False

    def read(self, n):
        if self._read:
            return b""
        self._read = True
        return self._body


class TestDownloadResume(unittest.TestCase):
    def test_server_ignoring_range_does_not_corrupt_file(self):
        with tempfile.TemporaryDirectory() as d:
            dest = Path(d) / "m.bin"
            (Path(d) / "m.bin.part").write_bytes(b"STALE")
            w = ModelDownloadWorker("m", "http://x/m.bin", dest)
            with mock.patch("urllib.request.urlopen", return_value=_FakeResponse(200, b"FULLBODY")):
                w.run()
            self.assertEqual(dest.read_bytes(), b"FULLBODY")

    def test_416_with_complete_part_file_finishes(self):
        with tempfile.TemporaryDirectory() as d:
            dest = Path(d) / "m.bin"
            (Path(d) / "m.bin.part").write_bytes(b"COMPLETE")
            w = ModelDownloadWorker("m", "http://x/m.bin", dest)
            err = urllib.error.HTTPError("http://x", 416, "range", {}, None)
            with mock.patch("urllib.request.urlopen", side_effect=err):
                w.run()
            self.assertEqual(dest.read_bytes(), b"COMPLETE")


if __name__ == "__main__":
    unittest.main()
