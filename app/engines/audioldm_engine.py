from __future__ import annotations

import importlib.util
from collections.abc import Callable

import numpy as np

from app.core.config import config_manager
from app.core.device import device_manager
from app.data.model_catalog import get_model, is_model_present
from app.engines.base import EngineLicense, ParamSpec, SoundEngine, SoundParameters

MODEL_ID = "audioldm-s"
REQUIRED_PACKAGES = ("diffusers", "transformers", "torch")


class AudioLdmEngine(SoundEngine):
    model_id = MODEL_ID
    max_duration_seconds = 30.0
    kinds = ("sfx",)
    supports_negative_prompt = True
    controls = (
        ParamSpec("steps", "Steps", 1, 200, 1, 20, description="More steps refine the sound but take longer."),
        ParamSpec("guidance", "Prompt strength", 0, 20, 0.5, 3.5, description="How closely the sound follows your description."),
    )

    def __init__(self) -> None:
        self._pipeline = None
        self._device = "cpu"

    @property
    def name(self) -> str:
        return "AudioLDM"

    @property
    def license_info(self) -> EngineLicense:
        return EngineLicense(
            name="CC BY-NC-SA 4.0",
            url="https://huggingface.co/cvssp/audioldm-s-full-v2",
            commercial_permitted=False,
            notice="Non-commercial use only.",
        )

    @property
    def requires_gpu_recommended(self) -> bool:
        return True

    @property
    def native_sample_rate(self) -> int:
        return 16000

    def unavailable_reason(self) -> str | None:
        missing = [pkg for pkg in REQUIRED_PACKAGES if importlib.util.find_spec(pkg) is None]
        if missing:
            return f"Missing Python packages: {', '.join(missing)}"
        if not self._weights_present():
            return "Download AudioLDM from the Models page first"
        return None

    def is_available(self) -> bool:
        return self.unavailable_reason() is None

    def is_loaded(self) -> bool:
        return self._pipeline is not None

    def get_default_params(self) -> SoundParameters:
        return SoundParameters(duration_seconds=5.0, steps=20, guidance=3.5, negative_prompt="Low quality.")

    def _weights_present(self) -> bool:
        model = get_model(MODEL_ID)
        return model is not None and is_model_present(model, config_manager.get_models_directory())

    def load_model(self, progress_callback: Callable[[float, str], None] | None = None) -> bool:
        if self._pipeline is not None:
            return True
        if not self._weights_present():
            raise RuntimeError("Download AudioLDM from the Models page first.")
        import torch
        from diffusers import AudioLDMPipeline

        self._device = device_manager.get_preferred_device(config_manager.config.device_preference)
        dtype = torch.float32 if self._device == "cpu" else torch.float16
        if progress_callback:
            progress_callback(30.0, f"Loading AudioLDM on {self._device.upper()}")
        path = config_manager.get_models_directory() / "audioldm-s"
        self._pipeline = AudioLDMPipeline.from_pretrained(str(path), torch_dtype=dtype).to(self._device)
        return True

    def unload_model(self) -> None:
        self._pipeline = None
        device_manager.clear_cache()

    def generate(
        self,
        prompt: str,
        params: SoundParameters,
        on_step: Callable[[int, int], None] | None = None,
    ) -> tuple[np.ndarray, int]:
        import torch

        pipeline = self._pipeline
        if pipeline is None:
            raise RuntimeError("AudioLDM is not loaded.")

        def step_callback(step: int, _timestep, _latents) -> None:
            if on_step is not None:
                on_step(step + 1, params.steps)

        generator = torch.Generator("cpu").manual_seed(params.seed)
        duration = min(params.duration_seconds, self.max_duration_seconds)
        result = pipeline(
            prompt=prompt,
            negative_prompt=params.negative_prompt or None,
            num_inference_steps=params.steps,
            guidance_scale=params.guidance,
            audio_length_in_s=duration,
            generator=generator,
            callback=step_callback,
            callback_steps=1,
        )
        samples = np.asarray(result.audios[0], dtype=np.float32)
        return np.ascontiguousarray(samples), self.native_sample_rate
