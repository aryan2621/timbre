from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import numpy as np

from app.core.config import config_manager
from app.core.logging_setup import get_logger
from app.data.model_catalog import get_model, is_model_present
from app.engines.base import EngineLicense, ParamSpec, SynthesisParameters, TTSEngine

logger = get_logger("woof")

MODEL_ID = "underdog-woof"
VOICES = ("juno", "mira")


class WoofEngine(TTSEngine):
    """Underdog Woof: 40 MB numpy-only English voice with two fixed voices. Runs on the CPU."""

    model_id = MODEL_ID
    controls = (
        ParamSpec("voice", "Voice", kind="select", options=VOICES, default=VOICES[0]),
        ParamSpec("temperature", "Variation", 0.1, 1.5, 0.05, 0.5, description="Higher is livelier and less predictable."),
    )

    def __init__(self) -> None:
        self._voices: dict[str, object] = {}

    @property
    def name(self) -> str:
        return "Underdog Woof"

    @property
    def license_info(self) -> EngineLicense:
        return EngineLicense(
            name="Underdog Non-Commercial License 1.0",
            url="https://huggingface.co/ConwayResearch/Underdog-Woof/blob/main/LICENSE",
            commercial_permitted=False,
            notice='Free for non-commercial use with credit: show "Voice by Underdog Woof" in anything you publish with its audio. Commercial use needs a licence from Conway (license@conway.tech).',
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
    def _weights(self) -> Path:
        return config_manager.get_models_directory() / "underdog-woof" / "woof_int8.npz"

    def is_available(self) -> bool:
        model = get_model(MODEL_ID)
        return model is not None and is_model_present(model, config_manager.get_models_directory())

    def unavailable_reason(self) -> str | None:
        return None if self.is_available() else "Download Underdog Woof from the Models page first"

    def is_loaded(self) -> bool:
        return bool(self._voices)

    def get_default_params(self) -> SynthesisParameters:
        return SynthesisParameters(temperature=0.5, language="en", enable_watermark=False)

    def _voice(self, voice: str):
        if voice not in self._voices:
            from app.vendor.underdog_woof import Woof

            self._voices[voice] = Woof(weights=str(self._weights), voice=voice)
        return self._voices[voice]

    def load_model(self, progress_callback: Callable[[float, str], None] | None = None) -> bool:
        if not self.is_available():
            return False
        if progress_callback:
            progress_callback(30.0, "Loading Underdog Woof")
        self._voice(VOICES[0])
        return True

    def unload_model(self) -> None:
        self._voices.clear()

    def clone_and_synthesize(
        self, text: str, reference_audio_path: str | Path, params: SynthesisParameters
    ) -> tuple[np.ndarray, int]:
        voice = str(params.extra.get("voice") or VOICES[0])
        if voice not in VOICES:
            raise ValueError(f"Unknown Woof voice: {voice}")
        tts = self._voice(voice)
        tts.temp = float(params.temperature)
        audio = tts(text, seed=params.seed if params.seed >= 0 else None)
        return np.ascontiguousarray(audio, dtype=np.float32), 24000
