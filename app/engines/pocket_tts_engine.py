from __future__ import annotations

import importlib.util
import os
import re
from collections.abc import Callable
from pathlib import Path

import numpy as np

from app.core.config import config_manager
from app.core.logging_setup import get_logger
from app.engines.base import EngineLicense, ParamSpec, SynthesisParameters, TTSEngine

logger = get_logger("pocket_tts")

LANGUAGE = "english_2026-10"
HF_URL = re.compile(r"hf://\S+?/(model\.safetensors|tokenizer\.json)(@\S+)?")


class PocketTTSEngine(TTSEngine):
    model_id = "pocket-tts"
    controls = (
        ParamSpec("temperature", "Variation", 0.0, 2.0, 0.05, 0.3, description="Higher is livelier and less predictable."),
        ParamSpec("lsd_decode_steps", "Quality steps", 1, 16, 1, 1, description="More steps sound cleaner but render slower."),
        ParamSpec("eos_threshold", "Ending threshold", -10.0, 2.0, 0.1, -4.0, description="Higher keeps speaking longer before it stops."),
        ParamSpec("speed", "Speed", 0.25, 4.0, 0.05, 1.0, group="delivery"),
    )

    def __init__(self) -> None:
        self._model = None
        self._settings: tuple = ()
        self._states: dict[tuple[str, float], object] = {}

    @property
    def name(self) -> str:
        return "Pocket TTS"

    @property
    def license_info(self) -> EngineLicense:
        return EngineLicense(
            name="CC BY 4.0",
            url="https://creativecommons.org/licenses/by/4.0/",
            commercial_permitted=True,
            notice="Pocket TTS by Kyutai is CC BY 4.0. Credit Kyutai when you publish audio made with it.",
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

    @property
    def _weights_dir(self) -> Path:
        return config_manager.get_models_directory() / "pocket-tts"

    def is_available(self) -> bool:
        weights = self._weights_dir
        return (
            importlib.util.find_spec("pocket_tts") is not None
            and (weights / "model.safetensors").is_file()
            and (weights / "tokenizer.json").is_file()
        )

    def unavailable_reason(self) -> str | None:
        if importlib.util.find_spec("pocket_tts") is None:
            return "Its Python package is not installed in the API environment"
        if not self.is_available():
            return "Download Pocket TTS from the Models page first"
        return None

    def is_loaded(self) -> bool:
        return self._model is not None

    def get_default_params(self) -> SynthesisParameters:
        return SynthesisParameters(temperature=0.3, speed=1.0, language="en", enable_watermark=False)

    def _local_config(self) -> Path:
        import pocket_tts

        packaged = Path(pocket_tts.__file__).parent / "config" / f"{LANGUAGE}.yaml"
        files = {name: str(self._weights_dir / name) for name in ("model.safetensors", "tokenizer.json")}
        text = HF_URL.sub(lambda match: files[match.group(1)], packaged.read_text())
        target = self._weights_dir / "config.yaml"
        target.write_text(text)
        return target

    def load_model(self, progress_callback: Callable[[float, str], None] | None = None) -> bool:
        if self._model is not None:
            return True
        if not self.is_available():
            return False
        try:
            from pocket_tts import TTSModel

            if progress_callback:
                progress_callback(30.0, "Loading Pocket TTS")
            self._settings = self._settings or self._pick(self.get_default_params())
            temp, steps, eos = self._settings
            self._model = TTSModel.load_model(
                config=self._local_config(), temp=temp, lsd_decode_steps=steps, eos_threshold=eos
            )
            return True
        except Exception as exc:  # noqa: BLE001 - surfaced as "could not load" by the job runner
            logger.error("Failed to load Pocket TTS: %s", exc)
            self._model = None
            return False

    @staticmethod
    def _pick(params: SynthesisParameters) -> tuple[float, int, float]:
        return (
            float(params.temperature),
            int(params.extra.get("lsd_decode_steps", 1)),
            float(params.extra.get("eos_threshold", -4.0)),
        )

    def unload_model(self) -> None:
        self._model = None
        self._states.clear()

    def clone_and_synthesize(
        self, text: str, reference_audio_path: str | Path, params: SynthesisParameters
    ) -> tuple[np.ndarray, int]:
        wanted = self._pick(params)
        if self._model is not None and wanted != self._settings:
            self._model = None
            self._states.clear()
            self._settings = wanted
            self.load_model()
        model = self._model
        if model is None:
            raise RuntimeError("Pocket TTS is not loaded.")
        reference = str(reference_audio_path or "")
        if not reference:
            raise RuntimeError("A reference audio path is required for voice cloning.")
        key = (os.path.realpath(reference), os.path.getmtime(reference))
        state = self._states.get(key)
        if state is None:
            state = self._states[key] = model.get_state_for_audio_prompt(reference)
        audio = model.generate_audio(state, text)
        return audio.detach().cpu().numpy().astype(np.float32), int(model.sample_rate)
