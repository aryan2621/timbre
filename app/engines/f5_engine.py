"""
F5-TTS Engine Adapter (MIT License).
Diffusion Transformer zero-shot speech synthesis with Flow Matching.
"""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import random
import time
from typing import Callable, List, Optional, Tuple

try:
    import numpy as np
except ImportError:
    np = None

from app.core.config import config_manager
from app.core.device import device_manager
from app.core.logging_setup import get_logger
from app.core.paths import paths
from app.engines.base import EngineLicense, SynthesisParameters, TTSEngine
from app.engines.chatterbox_engine import PerthWatermark

logger = get_logger("f5_tts")


class F5Engine(TTSEngine):
    """Adapter for F5-TTS Flow-matching diffusion zero-shot voice cloning."""

    def __init__(self) -> None:
        self._is_loaded = False
        self._model = None
        self._device = "cpu"

    @property
    def _weights_dir(self) -> Path:
        return config_manager.get_models_directory() / "f5_tts"

    @property
    def name(self) -> str:
        return "F5-TTS"

    @property
    def license_info(self) -> EngineLicense:
        return EngineLicense(
            name="MIT License",
            url="https://opensource.org/licenses/MIT",
            commercial_permitted=True,
            notice="F5-TTS is released under the MIT License and permits commercial and non-commercial local use.",
            requires_consent_warning=True,
        )

    @property
    def supported_languages(self) -> List[str]:
        return ["en", "zh"]

    @property
    def requires_gpu_recommended(self) -> bool:
        return True  # Diffusion sampling steps benefit significantly from GPU acceleration

    @property
    def native_sample_rate(self) -> int:
        return 24000

    def is_available(self) -> bool:
        """True only when the F5-TTS runtime is importable."""
        return importlib.util.find_spec("f5_tts") is not None

    def is_loaded(self) -> bool:
        return self._is_loaded

    def get_default_params(self) -> SynthesisParameters:
        return SynthesisParameters(
            temperature=0.8,
            cfg_weight=2.0,
            exaggeration=1.0,
            speed=1.0,
            seed=-1,
            top_p=0.9,
            repetition_penalty=1.5,
            language="en",
            enable_watermark=True,
        )

    def load_model(self, progress_callback: Optional[Callable[[float, str], None]] = None) -> bool:
        if self._is_loaded:
            return True

        self._device = device_manager.get_preferred_device(config_manager.config.device_preference)
        logger.info("Loading F5-TTS on %s", self._device)

        if progress_callback:
            progress_callback(20.0, f"Initializing F5-TTS DiT weights on {self._device.upper()}")

        try:
            # Check for f5_tts library if available
            try:
                from f5_tts.api import F5TTS  # type: ignore
                if progress_callback:
                    progress_callback(70.0, "Loading Flow Matching vocoder")
                self._model = F5TTS(device=self._device)
                logger.info("Loaded native f5_tts pipeline.")
            except ImportError:
                logger.error(
                    "The f5-tts package is not installed. "
                    "Install it with: pip install f5-tts"
                )
                self._is_loaded = False
                return False

            if progress_callback:
                progress_callback(100.0, "F5-TTS model ready.")

            self._is_loaded = True
            return True
        except Exception as e:
            logger.error("Failed to load F5-TTS: %s", e)
            self._is_loaded = False
            return False

    def unload_model(self) -> None:
        logger.info("Unloading F5-TTS.")
        self._model = None
        self._is_loaded = False
        device_manager.clear_cache()

    def clone_and_synthesize(
        self,
        text: str,
        reference_audio_path: str | Path,
        params: SynthesisParameters,
    ) -> Tuple[np.ndarray, int]:
        if not self._is_loaded:
            self.load_model()

        if not text.strip():
            return np.zeros(0, dtype=np.float32), self.native_sample_rate

        # If f5_tts library is loaded
        if hasattr(self._model, "infer"):
            try:
                wav, sr, _ = self._model.infer(
                    ref_file=str(reference_audio_path),
                    ref_text="",
                    gen_text=text,
                    speed=params.speed,
                    cfg_strength=params.cfg_weight,
                )
                if params.enable_watermark:
                    wav = PerthWatermark.apply(wav, sr)
                return wav, sr
            except Exception as e:
                logger.error("F5 native synthesis failed: %s", e)
                raise RuntimeError(f"F5-TTS synthesis failed: {e}") from e

        raise RuntimeError(
            "F5-TTS is not available. Install the runtime with `pip install f5-tts`."
        )

    def synthesize_chunk(
        self,
        text: str,
        reference_audio_path: str | Path,
        params: SynthesisParameters,
    ) -> Tuple[np.ndarray, int]:
        """Synthesize a single chunk for streaming playback."""
        return self.clone_and_synthesize(text, reference_audio_path, params)
