from __future__ import annotations

import importlib.util
from collections.abc import Callable

import numpy as np

from app.core.config import config_manager
from app.core.device import device_manager
from app.core.logging_setup import get_logger
from app.data.model_catalog import get_model, is_model_present
from app.engines.base import EngineLicense, ParamSpec, SoundEngine, SoundParameters

logger = get_logger("stable_audio")

MODEL_ID = "stable-audio-open"
REQUIRED_PACKAGES = ("diffusers", "transformers", "torch", "torchsde")


def _noise_free_final_step(scheduler_class):
    import torch

    class _FinalStepSafe:
        def __init__(self, sampler):
            self._sampler = sampler

        def __call__(self, sigma, next_sigma):
            if float(next_sigma) <= 0.0:
                return torch.zeros(())
            return self._sampler(sigma, next_sigma)

    class NoiseFreeFinalStep(scheduler_class):
        @property
        def noise_sampler(self):
            return self._wrapped_sampler

        @noise_sampler.setter
        def noise_sampler(self, sampler):
            self._wrapped_sampler = None if sampler is None else _FinalStepSafe(sampler)

    return NoiseFreeFinalStep


class StableAudioEngine(SoundEngine):
    model_id = MODEL_ID
    max_duration_seconds = 47.0
    controls = (
        ParamSpec("steps", "Steps", 1, 500, 5, 100, description="More steps refine the sound but take longer."),
        ParamSpec("guidance", "Prompt strength", 0, 30, 0.5, 7.0, description="How closely the sound follows your description."),
    )

    def __init__(self) -> None:
        self._pipeline = None
        self._device = "cpu"

    @property
    def name(self) -> str:
        return "Stable Audio Open"

    @property
    def license_info(self) -> EngineLicense:
        return EngineLicense(
            name="Stability AI Community License",
            url="https://huggingface.co/stabilityai/stable-audio-open-1.0/blob/main/LICENSE.md",
            commercial_permitted=True,
            notice="Free for individuals and organisations under $1M annual revenue.",
        )

    @property
    def requires_gpu_recommended(self) -> bool:
        return True

    @property
    def native_sample_rate(self) -> int:
        return 44100

    def unavailable_reason(self) -> str | None:
        missing = [pkg for pkg in REQUIRED_PACKAGES if importlib.util.find_spec(pkg) is None]
        if missing:
            return f"Missing Python packages: {', '.join(missing)}"
        return None

    def is_available(self) -> bool:
        return self.unavailable_reason() is None and self._weights_present()

    def is_loaded(self) -> bool:
        return self._pipeline is not None

    def get_default_params(self) -> SoundParameters:
        return SoundParameters(
            duration_seconds=10.0, steps=100, guidance=7.0, negative_prompt="Low quality."
        )

    def _weights_present(self) -> bool:
        model = get_model(MODEL_ID)
        return model is not None and is_model_present(model, config_manager.get_models_directory())

    def load_model(self, progress_callback: Callable[[float, str], None] | None = None) -> bool:
        if self._pipeline is not None:
            return True
        if not self._weights_present():
            raise RuntimeError("Download Stable Audio Open from the Models page first.")

        import torch
        from diffusers import StableAudioPipeline

        self._device = device_manager.get_preferred_device(config_manager.config.device_preference)
        dtype = torch.float32 if self._device == "cpu" else torch.float16
        weights_dir = config_manager.get_models_directory() / "stable-audio-open"
        if progress_callback:
            progress_callback(30.0, f"Loading Stable Audio Open on {self._device.upper()}")
        pipeline = StableAudioPipeline.from_pretrained(str(weights_dir), torch_dtype=dtype)
        pipeline.scheduler = _noise_free_final_step(type(pipeline.scheduler)).from_config(
            pipeline.scheduler.config
        )
        self._pipeline = pipeline.to(self._device)
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
            raise RuntimeError("Stable Audio Open is not loaded.")

        def step_callback(step: int, _timestep, _latents) -> None:
            if on_step is not None:
                on_step(step + 1, params.steps)

        generator_device = "cpu" if self._device == "mps" else self._device
        generator = torch.Generator(generator_device).manual_seed(params.seed)
        duration = min(params.duration_seconds, self.max_duration_seconds)
        result = pipeline(
            prompt=prompt,
            negative_prompt=params.negative_prompt or None,
            num_inference_steps=params.steps,
            guidance_scale=params.guidance,
            audio_end_in_s=duration,
            num_waveforms_per_prompt=1,
            generator=generator,
            callback=step_callback,
            callback_steps=1,
        )
        sample_rate = int(pipeline.vae.sampling_rate)
        samples = result.audios[0].float().cpu().numpy().T
        trimmed = samples[: int(duration * sample_rate)]
        return np.ascontiguousarray(trimmed, dtype=np.float32), sample_rate
