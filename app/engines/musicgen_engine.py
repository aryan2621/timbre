from __future__ import annotations

import importlib.util
from collections.abc import Callable

import numpy as np

from app.core.config import config_manager
from app.core.device import device_manager
from app.data.model_catalog import get_model, is_model_present
from app.engines.base import EngineLicense, ParamSpec, SoundEngine, SoundParameters

MODEL_ID = "musicgen-small"
TOKENS_PER_SECOND = 50
REQUIRED_PACKAGES = ("transformers", "torch")


class _Progress:
    def __init__(self, total: int, on_step: Callable[[int, int], None] | None) -> None:
        self._total = total
        self._on_step = on_step
        self._count = 0

    def put(self, _value) -> None:
        self._count += 1
        if self._on_step is not None:
            self._on_step(min(self._count, self._total), self._total)

    def end(self) -> None:
        pass


class MusicGenEngine(SoundEngine):
    model_id = MODEL_ID
    max_duration_seconds = 40.0
    kinds = ("music",)
    supports_negative_prompt = False
    controls = (
        ParamSpec("guidance", "Prompt strength", 0, 20, 0.5, 3.0, description="How closely the music follows your description."),
        ParamSpec("temperature", "Variation", 0.1, 2.0, 0.05, 1.0, description="Higher is more adventurous."),
        ParamSpec("top_k", "Top-k", 0, 2000, 10, 250, description="Limits each note to the most likely choices. 0 turns it off."),
        ParamSpec("top_p", "Top-p", 0, 1, 0.01, 0, description="Nucleus sampling. 0 turns it off."),
    )

    def __init__(self) -> None:
        self._model = None
        self._processor = None
        self._device = "cpu"

    @property
    def name(self) -> str:
        return "MusicGen small"

    @property
    def license_info(self) -> EngineLicense:
        return EngineLicense(
            name="CC BY-NC 4.0",
            url="https://huggingface.co/facebook/musicgen-small",
            commercial_permitted=False,
            notice="Non-commercial use only.",
        )

    @property
    def requires_gpu_recommended(self) -> bool:
        return True

    @property
    def native_sample_rate(self) -> int:
        return 32000

    def unavailable_reason(self) -> str | None:
        missing = [pkg for pkg in REQUIRED_PACKAGES if importlib.util.find_spec(pkg) is None]
        if missing:
            return f"Missing Python packages: {', '.join(missing)}"
        if not self._weights_present():
            return "Download MusicGen small from the Models page first"
        return None

    def is_available(self) -> bool:
        return self.unavailable_reason() is None

    def is_loaded(self) -> bool:
        return self._model is not None

    def get_default_params(self) -> SoundParameters:
        return SoundParameters(duration_seconds=10.0, steps=1, guidance=3.0)

    def _weights_present(self) -> bool:
        model = get_model(MODEL_ID)
        return model is not None and is_model_present(model, config_manager.get_models_directory())

    def load_model(self, progress_callback: Callable[[float, str], None] | None = None) -> bool:
        if self._model is not None:
            return True
        if not self._weights_present():
            raise RuntimeError("Download MusicGen small from the Models page first.")
        from transformers import AutoProcessor, MusicgenForConditionalGeneration

        self._device = "cpu"
        if progress_callback:
            progress_callback(30.0, f"Loading MusicGen on {self._device.upper()}")
        path = str(config_manager.get_models_directory() / "musicgen-small")
        self._processor = AutoProcessor.from_pretrained(path)
        self._model = MusicgenForConditionalGeneration.from_pretrained(path).to(self._device)
        return True

    def unload_model(self) -> None:
        self._model = None
        self._processor = None
        device_manager.clear_cache()

    def generate(
        self,
        prompt: str,
        params: SoundParameters,
        on_step: Callable[[int, int], None] | None = None,
    ) -> tuple[np.ndarray, int]:
        import torch

        if self._model is None or self._processor is None:
            raise RuntimeError("MusicGen is not loaded.")
        duration = min(params.duration_seconds, self.max_duration_seconds)
        tokens = int(duration * TOKENS_PER_SECOND)
        torch.manual_seed(params.seed)
        inputs = self._processor(text=[prompt], padding=True, return_tensors="pt").to(self._device)
        audio = self._model.generate(
            **inputs,
            do_sample=True,
            temperature=float(params.extra.get("temperature", 1.0)),
            top_k=int(params.extra.get("top_k", 250)),
            top_p=float(params.extra.get("top_p", 0.0)) or 1.0,
            guidance_scale=params.guidance,
            max_new_tokens=tokens,
            streamer=_Progress(tokens, on_step),
        )
        samples = audio[0, 0].float().cpu().numpy()
        return np.ascontiguousarray(samples, dtype=np.float32), self.native_sample_rate
