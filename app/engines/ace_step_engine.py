from __future__ import annotations

import io
import json
import time
import urllib.request
from collections.abc import Callable
from email import message_from_bytes
from email.policy import default

import numpy as np
import soundfile as sf

from app.core.config import config_manager
from app.core.logging_setup import get_logger
from app.data.model_catalog import get_model, is_model_present, model_local_path
from app.engines.base import EngineLicense, ParamSpec, SoundEngine, SoundParameters
from app.runtimes.native import NativeServer

logger = get_logger("ace_step")

MODEL_ID = "ace-step"
POLL_INTERVAL_SECONDS = 0.5
PHASES = 2
INSTRUMENTAL = "[Instrumental]"


class AceStepEngine(SoundEngine):
    model_id = MODEL_ID
    kinds = ("music",)
    supports_lyrics = True
    supports_negative_prompt = False
    max_duration_seconds = 600.0
    controls = (
        ParamSpec("steps", "Steps", 1, 200, 1, 8, description="Turbo is tuned for 8."),
        ParamSpec("guidance_scale", "Prompt strength", 0, 20, 0.5, 0, description="0 picks the model's own value."),
        ParamSpec("shift", "Shift", 0, 10, 0.5, 0, description="Timestep shift. 0 picks the model's own value."),
        ParamSpec("bpm", "Tempo (BPM)", 0, 300, 1, 0, description="0 lets the model choose."),
        ParamSpec("keyscale", "Key", kind="select", default="", options=("", "C major", "C minor", "C# major", "C# minor", "D major", "D minor", "Eb major", "Eb minor", "E major", "E minor", "F major", "F minor", "F# major", "F# minor", "G major", "G minor", "Ab major", "Ab minor", "A major", "A minor", "Bb major", "Bb minor", "B major", "B minor")),
        ParamSpec("timesignature", "Time signature", kind="select", default="", options=("", "2", "3", "4", "6")),
        ParamSpec("vocal_language", "Vocal language", kind="select", default="", options=("", "en", "es", "fr", "de", "it", "pt", "ja", "ko", "zh", "ru", "hi", "ar")),
        ParamSpec("lm_temperature", "Composer variation", 0, 2, 0.05, 0.85, group="advanced", description="Randomness of the planning step."),
        ParamSpec("lm_cfg_scale", "Composer strength", 0, 10, 0.5, 2.0, group="advanced"),
        ParamSpec("lm_top_p", "Composer top-p", 0, 1, 0.01, 0.9, group="advanced"),
        ParamSpec("lm_top_k", "Composer top-k", 0, 500, 5, 0, group="advanced", description="0 turns it off."),
        ParamSpec("solver", "Solver", kind="select", default="euler", options=("euler", "stork4"), group="advanced"),
    )

    def __init__(self) -> None:
        self._server = NativeServer("ace-server", "music")

    @property
    def name(self) -> str:
        return "ACE-Step"

    @property
    def license_info(self) -> EngineLicense:
        return EngineLicense(
            name="Apache-2.0",
            url="https://huggingface.co/ACE-Step/Ace-Step1.5",
            commercial_permitted=True,
            notice="Songs with optional lyrics, up to four minutes.",
        )

    @property
    def requires_gpu_recommended(self) -> bool:
        return True

    @property
    def native_sample_rate(self) -> int:
        return 48000

    def unavailable_reason(self) -> str | None:
        return None if self._server.is_available() else "The music engine is not bundled with this build."

    def is_available(self) -> bool:
        model = get_model(MODEL_ID)
        return (
            model is not None
            and is_model_present(model, config_manager.get_models_directory())
            and self._server.is_available()
        )

    def is_loaded(self) -> bool:
        return self._server.is_running()

    def get_default_params(self) -> SoundParameters:
        return SoundParameters(duration_seconds=30.0, steps=8, guidance=1.0)

    def load_model(self, progress_callback: Callable[[float, str], None] | None = None) -> bool:
        model = get_model(MODEL_ID)
        models_dir = config_manager.get_models_directory()
        if model is None or not is_model_present(model, models_dir):
            raise RuntimeError("Download ACE-Step from the Models page first.")
        if progress_callback:
            progress_callback(30.0, "Starting ACE-Step")
        self._server.ensure(["--models", str(model_local_path(model, models_dir))])
        return True

    def unload_model(self) -> None:
        self._server.stop()

    def _submit(self, endpoint: str, body: dict | list) -> str:
        request = urllib.request.Request(
            self._server.url + endpoint,
            data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json"},
        )
        return str(self._server.send(request)["id"])

    def _await(self, job_id: str, phase: int, on_step: Callable[[int, int], None] | None) -> bytes:
        status_url = f"{self._server.url}/job?id={job_id}"
        try:
            while True:
                if on_step is not None:
                    on_step(phase, PHASES)
                status = self._server.send(urllib.request.Request(status_url))["status"]
                if status == "done":
                    return self._server.read(urllib.request.Request(status_url + "&result=1"))
                if status in ("failed", "cancelled"):
                    raise RuntimeError(f"ACE-Step {status}. See ace-server.log in the logs folder.")
                time.sleep(POLL_INTERVAL_SECONDS)
        except BaseException:
            self._cancel(job_id)
            raise

    def _cancel(self, job_id: str) -> None:
        try:
            self._server.send(urllib.request.Request(f"{self._server.url}/job?id={job_id}&cancel=1", method="POST"))
        except RuntimeError:
            logger.debug("Could not cancel ACE-Step job %s", job_id, exc_info=True)

    @staticmethod
    def _audio_part(body: bytes) -> bytes:
        message = message_from_bytes(b"Content-Type: multipart/mixed; boundary=ace-batch-boundary\r\n\r\n" + body, policy=default)
        for part in message.iter_parts():
            if part.get_content_type().startswith("audio/"):
                return part.get_payload(decode=True)
        raise RuntimeError("ACE-Step returned no audio.")

    @staticmethod
    def _extras(params: SoundParameters) -> dict:
        numbers = {"guidance_scale", "shift", "bpm", "lm_temperature", "lm_cfg_scale", "lm_top_p", "lm_top_k"}
        words = {"keyscale", "timesignature", "vocal_language", "solver"}
        out: dict = {key: value for key, value in params.extra.items() if key in numbers and value != ""}
        out.update({key: value for key, value in params.extra.items() if key in words and value != ""})
        for key in ("bpm", "lm_top_k"):
            if key in out:
                out[key] = int(out[key])
        return out

    def generate(
        self,
        prompt: str,
        params: SoundParameters,
        on_step: Callable[[int, int], None] | None = None,
    ) -> tuple[np.ndarray, int]:
        if not self.is_loaded():
            raise RuntimeError("ACE-Step is not loaded.")
        request = {
            "caption": prompt,
            "lyrics": params.lyrics.strip() or INSTRUMENTAL,
            "duration": min(params.duration_seconds, self.max_duration_seconds),
            "seed": params.seed,
            "inference_steps": params.steps,
            "output_format": "wav16",
            **self._extras(params),
        }
        enriched = json.loads(self._await(self._submit("/lm", request), 0, on_step))
        audio = self._audio_part(self._await(self._submit("/synth", enriched), 1, on_step))
        samples, sample_rate = sf.read(io.BytesIO(audio), dtype="float32", always_2d=True)
        return np.ascontiguousarray(samples), int(sample_rate)
