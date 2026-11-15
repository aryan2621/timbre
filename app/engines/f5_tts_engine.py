from __future__ import annotations

import importlib.util
from collections.abc import Callable
from pathlib import Path

import numpy as np

from app.core.config import config_manager
from app.core.device import device_manager
from app.core.logging_setup import get_logger
from app.data.model_catalog import get_model, is_model_present
from app.engines.base import EngineLicense, ParamSpec, SynthesisParameters, TTSEngine
from app.engines.mlx_audio_engine import reference_transcript

logger = get_logger("f5_tts")

MODEL_ID = "f5-tts-v1"


class F5TTSEngine(TTSEngine):
    model_id = MODEL_ID
    controls = (
        ParamSpec("nfe_step", "Quality steps", 8, 64, 1, 32, description="More steps sound cleaner but render slower."),
        ParamSpec("cfg_strength", "Voice match", 0.0, 6.0, 0.1, 2.0, description="Higher follows the reference voice more closely."),
        ParamSpec("speed", "Speed", 0.5, 2.0, 0.05, 1.0, group="delivery"),
    )

    def __init__(self) -> None:
        self._model = None

    @property
    def name(self) -> str:
        return "F5-TTS"

    @property
    def license_info(self) -> EngineLicense:
        return EngineLicense(
            name="CC BY-NC 4.0",
            url="https://huggingface.co/SWivid/F5-TTS",
            commercial_permitted=False,
            notice="F5-TTS v1 Base by SWivid. The weights are non-commercial.",
        )

    @property
    def supported_languages(self) -> list[str]:
        return ["en", "zh"]

    @property
    def requires_gpu_recommended(self) -> bool:
        return True

    @property
    def native_sample_rate(self) -> int:
        return 24000

    @property
    def _weights_dir(self) -> Path:
        return config_manager.get_models_directory() / "f5-tts"

    def _weights_present(self) -> bool:
        model = get_model(MODEL_ID)
        return model is not None and is_model_present(model, config_manager.get_models_directory())

    def is_available(self) -> bool:
        return importlib.util.find_spec("f5_tts") is not None and self._weights_present()

    def unavailable_reason(self) -> str | None:
        if importlib.util.find_spec("f5_tts") is None:
            return "Its Python package is not installed in the API environment"
        if not self._weights_present():
            return "Download F5-TTS from the Models page first"
        return None

    def is_loaded(self) -> bool:
        return self._model is not None

    def get_default_params(self) -> SynthesisParameters:
        return SynthesisParameters(speed=1.0, language="en", enable_watermark=False)

    def load_model(self, progress_callback: Callable[[float, str], None] | None = None) -> bool:
        if self._model is not None:
            return True
        if not self.is_available():
            return False
        try:
            from f5_tts.api import F5TTS

            device = device_manager.get_preferred_device(config_manager.config.device_preference)
            if progress_callback:
                progress_callback(30.0, f"Loading F5-TTS on {device.upper()}")
            weights = self._weights_dir
            self._model = F5TTS(
                model="F5TTS_v1_Base",
                ckpt_file=str(weights / "model_1250000.safetensors"),
                vocab_file=str(weights / "vocab.txt"),
                vocoder_local_path=str(weights / "vocos"),  # local, so nothing is fetched at run time
                device=device,
            )
            return True
        except Exception as exc:  # noqa: BLE001 - surfaced as "could not load" by the job runner
            logger.error("Failed to load F5-TTS: %s", exc, exc_info=True)
            self._model = None
            return False

    def unload_model(self) -> None:
        self._model = None
        device_manager.clear_cache()

    def clone_and_synthesize(
        self, text: str, reference_audio_path: str | Path, params: SynthesisParameters
    ) -> tuple[np.ndarray, int]:
        model = self._model
        if model is None:
            raise RuntimeError("F5-TTS is not loaded.")
        reference = str(reference_audio_path or "")
        if not reference:
            raise RuntimeError("A reference audio path is required for voice cloning.")
        transcript = reference_transcript(reference)
        if not transcript:
            # An empty transcript would make F5 download Whisper-large on its own.
            raise RuntimeError("F5-TTS needs the reference clip's transcript. Download a Whisper model from the Models page.")
        wav, rate, _ = model.infer(
            ref_file=reference,
            ref_text=transcript,
            gen_text=text,
            nfe_step=int(params.extra.get("nfe_step", 32)),
            cfg_strength=float(params.extra.get("cfg_strength", 2.0)),
            speed=params.speed,
            seed=params.seed if params.seed >= 0 else None,
            show_info=lambda *_: None,
        )
        return np.ascontiguousarray(wav, dtype=np.float32), int(rate)
