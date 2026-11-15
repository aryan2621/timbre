from __future__ import annotations

import io
import json
import urllib.request
from collections.abc import Callable

import numpy as np
import soundfile as sf

from app.core.config import config_manager
from app.data.model_catalog import get_model, is_model_present, model_local_path
from app.engines.base import EngineLicense, ParamSpec, SoundEngine, SoundParameters
from app.runtimes.native import NativeServer

MODEL_ID = "stable-audio-open-small"

# stable-audio-tools needs its own Python and torch, so the model runs in a bundled server
# (desktop/sfx-server/serve.py) the same way the MLX voices and ACE-Step do.
SERVER = NativeServer("sfx-server", "sound effects")


class StableAudioSmallEngine(SoundEngine):
    model_id = MODEL_ID
    kinds = ("sfx",)
    max_duration_seconds = 11.0
    supports_negative_prompt = False
    controls = (
        ParamSpec("steps", "Steps", 1, 50, 1, 8, description="Tuned for 8. More steps rarely help this model."),
        ParamSpec("guidance", "Prompt strength", 0, 15, 0.5, 1.0, description="How closely the sound follows your description."),
    )

    @property
    def name(self) -> str:
        return "Stable Audio Open Small"

    @property
    def license_info(self) -> EngineLicense:
        return EngineLicense(
            name="Stability AI Community License",
            url="https://huggingface.co/stabilityai/stable-audio-open-small/blob/main/LICENSE",
            commercial_permitted=True,
            notice="Free for individuals and organisations under $1M annual revenue.",
        )

    @property
    def requires_gpu_recommended(self) -> bool:
        return True

    @property
    def native_sample_rate(self) -> int:
        return 44100

    def _weights_present(self) -> bool:
        model = get_model(MODEL_ID)
        return model is not None and is_model_present(model, config_manager.get_models_directory())

    def unavailable_reason(self) -> str | None:
        if not SERVER.is_available():
            return "Install the sound effects engine from the Models page first."
        if not self._weights_present():
            return "Download Stable Audio Open Small from the Models page first"
        return None

    def is_available(self) -> bool:
        return self.unavailable_reason() is None

    def is_loaded(self) -> bool:
        return SERVER.is_running()

    def get_default_params(self) -> SoundParameters:
        return SoundParameters(duration_seconds=8.0, steps=8, guidance=1.0)

    def load_model(self, progress_callback: Callable[[float, str], None] | None = None) -> bool:
        model = get_model(MODEL_ID)
        models_dir = config_manager.get_models_directory()
        if model is None or not is_model_present(model, models_dir):
            raise RuntimeError("Download Stable Audio Open Small from the Models page first.")
        if progress_callback:
            progress_callback(30.0, "Starting Stable Audio Open Small")
        SERVER.ensure(["--model-dir", str(model_local_path(model, models_dir))])
        return True

    def unload_model(self) -> None:
        SERVER.stop()  # the weights live in that process, so stopping it frees them

    def generate(
        self,
        prompt: str,
        params: SoundParameters,
        on_step: Callable[[int, int], None] | None = None,
    ) -> tuple[np.ndarray, int]:
        if not SERVER.is_running():
            raise RuntimeError("Stable Audio Open Small is not loaded.")
        body = {
            "prompt": prompt,
            "seconds": min(params.duration_seconds, self.max_duration_seconds),
            "steps": params.steps,
            "cfg_scale": params.guidance,
            "seed": params.seed,
        }
        data = SERVER.read(_post("/generate", body))
        samples, sample_rate = sf.read(io.BytesIO(data), dtype="float32", always_2d=True)
        if on_step is not None:
            on_step(params.steps, params.steps)  # one request per render, so progress jumps to done
        return np.ascontiguousarray(samples), int(sample_rate)


def _post(path: str, body: dict):
    return urllib.request.Request(
        SERVER.url + path, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"}
    )
