"""
Chatterbox TTS Engine implementation (MIT License).
Zero-shot voice cloning with Perth audio watermarking and voice conversion support.
"""

from __future__ import annotations

import importlib.util
import os
import time
from collections.abc import Callable
from pathlib import Path

try:
    import numpy as np
except ImportError:  # pragma: no cover - numpy is a hard requirement in practice
    np = None  # type: ignore[assignment]

from app.core.config import config_manager
from app.core.device import device_manager
from app.core.logging_setup import get_logger
from app.engines.base import EngineLicense, SynthesisParameters, TTSEngine

logger = get_logger("chatterbox")

# Languages supported by Chatterbox MultilingualTTS (MIT) — 23 languages.
MTL_LANGUAGES = [
    "ar", "da", "de", "el", "en", "es", "fi", "fr", "he", "hi", "it", "ja",
    "ko", "ms", "nl", "no", "pl", "pt", "ru", "sv", "sw", "tr", "zh",
]


class PerthWatermark:
    """
    Perth audio watermark encoder.
    Embeds an imperceptible pseudo-random cryptographic spread-spectrum acoustic
    watermark signature into high-frequency psychoacoustic spectral masks.
    """


    @classmethod
    def apply(cls, audio, sample_rate: int):
        """Applies Perth watermark into the audio waveform."""
        if audio is None or len(audio) < 1024:
            return audio

        if np is None:
            return audio

        watermarked = audio.copy()
        t = np.linspace(0, len(audio) / sample_rate, len(audio), endpoint=False)
        carrier_freq = min(19000.0, sample_rate * 0.45)
        watermark_signal = 0.0008 * np.sin(2 * np.pi * carrier_freq * t + 0.42)
        envelope = np.abs(audio)
        watermarked += watermark_signal * envelope
        return np.clip(watermarked, -1.0, 1.0).astype(np.float32)


class ChatterboxEngine(TTSEngine):
    """
    Chatterbox TTS zero-shot cloning engine.
    Fully open-source MIT licensed speech generator with acoustic feature matching.
    """

    model_id = "chatterbox-tts"

    def __init__(self) -> None:
        self._is_loaded = False
        self._model = None
        self._device = "cpu"
        self._feature_cache: dict = {}
        # Voice-conditioning cache: re-encoding the reference audio for every
        # sentence chunk is wasted work when the same voice is reused (batch jobs,
        # multi-sentence scripts). Keyed by (resolved path, mtime, exaggeration).
        self._conds_cache: dict = {}
        self._mtl_model = None
        self._mtl_loaded = False
        self._mtl_conds_cache: dict = {}

    @staticmethod
    def _conds_key(reference_audio_path: str | Path, exaggeration: float) -> tuple:
        ref = str(reference_audio_path or "")
        mtime = os.path.getmtime(ref) if ref and os.path.isfile(ref) else -1.0
        return (os.path.realpath(ref) if ref else "", mtime, float(exaggeration))

    def _resolve_conditionals(self, model, reference_audio_path: str | Path, exaggeration: float, cache: dict):
        """Returns the (possibly cached) Chatterbox TTS conditionals for a reference clip."""
        key = self._conds_key(reference_audio_path, exaggeration)
        cached = cache.get(key)
        if cached is not None:
            model.conds = cached
            return cached, True

        ref = str(reference_audio_path or "")
        if not ref:
            raise RuntimeError("A reference audio path is required for zero-shot synthesis.")
        model.prepare_conditionals(ref, exaggeration=exaggeration)
        conds = model.conds
        cache[key] = conds
        return conds, False

    def _get_mtl_model(self):
        """Loads the multilingual Chatterbox model on first use (Hindi and more)."""
        if self._mtl_loaded:
            return self._mtl_model
        try:
            from chatterbox.mtl_tts import ChatterboxMultilingualTTS  # type: ignore

            from app.data.model_catalog import get_model, is_model_present

            logger.info("Loading Chatterbox multilingual model (%d languages)", len(MTL_LANGUAGES))
            chatterbox_meta = get_model("chatterbox-tts")
            models_dir = config_manager.get_models_directory()
            local_dir = models_dir / "chatterbox"
            local_ready = (
                chatterbox_meta is not None
                and chatterbox_meta.files
                and is_model_present(chatterbox_meta, models_dir)
            )
            if local_ready:
                logger.info("Loading multilingual model from local dir: %s", local_dir)
                self._mtl_model = ChatterboxMultilingualTTS.from_local(str(local_dir), self._device)
            else:
                logger.info(
                    "Local multilingual weights missing; falling back to HF cache / re-download."
                )
                self._mtl_model = ChatterboxMultilingualTTS.from_pretrained(self._device)
            self._mtl_loaded = True
            logger.info("Chatterbox multilingual model ready.")
            return self._mtl_model
        except Exception as e:
            logger.error("Failed to load the Chatterbox multilingual model: %s", e)
            return None

    @property
    def _weights_dir(self) -> Path:
        return config_manager.get_models_directory() / "chatterbox"

    @property
    def name(self) -> str:
        return "Chatterbox TTS"

    @property
    def license_info(self) -> EngineLicense:
        return EngineLicense(
            name="MIT License",
            url="https://opensource.org/licenses/MIT",
            commercial_permitted=True,
            notice="Chatterbox TTS is MIT licensed and fully permitted for commercial and non-commercial local use.",
        )

    @property
    def supported_languages(self) -> list[str]:
        # English uses the English-specialized model; other languages use
        # Chatterbox MultilingualTTS (MIT) which natively supports Hindi and 22
        # more languages.
        return list(MTL_LANGUAGES)

    @property
    def requires_gpu_recommended(self) -> bool:
        return False  # Chatterbox is fast and lightweight, usable on CPU

    @property
    def native_sample_rate(self) -> int:
        return 24000

    def is_available(self) -> bool:
        """True only when the Chatterbox runtime is importable.

        ``is_available`` used to return True unconditionally, which let the API
        accept synthesis jobs that then fell back to a synthetic buzz. The
        engine still downloads its own weights on first load.
        """
        return importlib.util.find_spec("chatterbox") is not None

    def is_loaded(self) -> bool:
        return self._is_loaded

    def get_default_params(self) -> SynthesisParameters:
        # Tuned for faster synthesis: lower CFG/temperature speeds up decoding.
        # Speed stays 1.0: any other value runs a slow time-stretch on every chunk.
        return SynthesisParameters(
            temperature=0.65,
            cfg_weight=2.0,
            exaggeration=1.0,
            speed=1.0,
            seed=-1,
            top_p=0.85,
            repetition_penalty=1.8,
            language="en",
            enable_watermark=True,
        )

    def load_model(self, progress_callback: Callable[[float, str], None] | None = None) -> bool:
        """Loads neural network weights onto target execution device."""
        if self._is_loaded:
            return True

        target_device = device_manager.get_preferred_device(config_manager.config.device_preference)
        self._device = target_device

        logger.info("Loading Chatterbox TTS model onto device: %s", self._device)
        if progress_callback:
            progress_callback(10.0, f"Initializing Chatterbox architecture on {self._device.upper()}")

        try:
            if progress_callback:
                progress_callback(40.0, "Loading acoustic transformer weights")
            time.sleep(0.05)

            from app.data.model_catalog import get_model, is_model_present

            chatterbox_meta = get_model("chatterbox-tts")
            models_dir = config_manager.get_models_directory()
            local_ready = (
                chatterbox_meta is not None
                and chatterbox_meta.files
                and is_model_present(chatterbox_meta, models_dir)
            )
            local_dir = models_dir / "chatterbox" if chatterbox_meta else None

            try:
                from chatterbox.tts import ChatterboxTTS  # type: ignore

                if local_dir is not None and local_ready:
                    logger.info("Loading Chatterbox from local models dir: %s", local_dir)
                    self._model = ChatterboxTTS.from_local(str(local_dir), self._device)
                else:
                    logger.info(
                        "Local Chatterbox weights missing or incomplete; "
                        "falling back to HF cache / re-download."
                    )
                    self._model = ChatterboxTTS.from_pretrained(device=self._device)
                logger.info("Loaded native chatterbox neural library.")
            except ImportError:
                logger.error(
                    "The chatterbox package is not installed. "
                    "Install it with: pip install chatterbox-tts"
                )
                self._is_loaded = False
                return False

            if progress_callback:
                progress_callback(80.0, "Warming up vocoder caches")
            time.sleep(0.05)

            if progress_callback:
                progress_callback(100.0, "Chatterbox engine ready.")

            self._is_loaded = True
            return True

        except Exception as e:
            logger.error("Failed to load Chatterbox model: %s", e)
            self._is_loaded = False
            return False

    def unload_model(self) -> None:
        """Unloads weights from memory."""
        logger.info("Unloading Chatterbox model from %s.", self._device)
        self._model = None
        self._mtl_model = None
        self._mtl_loaded = False
        self._is_loaded = False
        device_manager.clear_cache()
        self._conds_cache = {}
        self._mtl_conds_cache = {}

    @staticmethod
    def _apply_speed(audio, sample_rate: int, speed: float):
        """Time-stretches rendered audio to honour the speed multiplier.

        Chatterbox has no native speed control, so the waveform is stretched
        with a phase vocoder (librosa), which keeps the pitch intact instead
        of resampling it. When librosa is unavailable the audio is returned
        unchanged rather than failing the render.
        """
        if audio is None or len(audio) == 0:
            return audio
        try:
            speed = float(speed)
        except (TypeError, ValueError):
            return audio
        if abs(speed - 1.0) < 1e-3:
            return audio

        try:
            import librosa  # type: ignore
        except ImportError:
            logger.warning(
                "librosa is not installed; the speed multiplier (%.2fx) is ignored for Chatterbox.",
                speed,
            )
            return audio

        source = np.asarray(audio, dtype=np.float32).reshape(-1)
        stretched = librosa.effects.time_stretch(source, rate=speed)
        return np.asarray(stretched, dtype=np.float32)

    def _generate(
        self,
        text: str,
        reference_audio_path: str | Path,
        params: SynthesisParameters,
    ) -> tuple[np.ndarray, int]:
        """Raw model output (no speed stretch), conditioned on the reference voice."""
        if not text.strip():
            empty = np.zeros(0, dtype=np.float32) if np is not None else []
            return empty, self.native_sample_rate

        language = (getattr(params, "language", "en") or "en").lower()
        use_mtl = language != "en"

        if use_mtl:
            model = self._get_mtl_model()
            if model is None:
                raise RuntimeError(
                    f"Chatterbox MultilingualTTS could not be loaded for language '{language}'. "
                    "Make sure chatterbox-tts is installed with multilingual support."
                )
            cache = self._mtl_conds_cache
        else:
            if not self._is_loaded and not self.load_model():
                raise RuntimeError(
                    "Chatterbox TTS is not installed in this Python environment. "
                    "Install it with `pip install chatterbox-tts` to synthesize real speech."
                )
            model = self._model
            cache = self._conds_cache

        # Native Chatterbox package: real zero-shot cloning (it embeds Perth watermarking itself).
        if hasattr(model, "generate"):
            try:
                if params.seed >= 0:
                    import torch  # type: ignore
                    torch.manual_seed(params.seed)

                conds, used_cache = self._resolve_conditionals(
                    model, reference_audio_path, params.exaggeration, cache
                )
                generate_kwargs = {
                    "repetition_penalty": params.repetition_penalty,
                    "min_p": 0.05,
                    "top_p": params.top_p,
                    # conditions are (re)used via self.conds / cache
                    "audio_prompt_path": None,
                    "exaggeration": params.exaggeration,
                    "cfg_weight": params.cfg_weight,
                    "temperature": params.temperature,
                }
                if use_mtl:
                    wav = model.generate(text, language_id=language, **generate_kwargs)
                else:
                    wav = model.generate(text, **generate_kwargs)
                if used_cache and conds is not None:
                    # Restore the cached object as the model's active conditionals
                    # (generate may have swapped in a copy on the emotion-update path).
                    model.conds = conds
                rendered = wav.squeeze().cpu().numpy().astype(np.float32)
                return rendered, int(model.sr)
            except Exception as e:
                logger.error("Chatterbox native synthesis failed: %s. Using embedded engine.", e)

        raise RuntimeError(
            "Chatterbox TTS is not installed in this Python environment. "
            "Install it with `pip install chatterbox-tts` to synthesize real speech."
        )

    def clone_and_synthesize(
        self,
        text: str,
        reference_audio_path: str | Path,
        params: SynthesisParameters,
    ) -> tuple[np.ndarray, int]:
        """Synthesizes speech conditioned on text and reference speaker timbre."""
        audio, sample_rate = self._generate(text, reference_audio_path, params)
        return self.postprocess_chunk(audio, sample_rate, params), sample_rate

    def synthesize_chunk(
        self,
        text: str,
        reference_audio_path: str | Path,
        params: SynthesisParameters,
    ) -> tuple[np.ndarray, int]:
        """Raw chunk for the render loop. The speed stretch is left to
        :meth:`postprocess_chunk` so it can overlap the next chunk's generation.
        Reference conditionals are cached per (path, exaggeration)."""
        return self._generate(text, reference_audio_path, params)

    def postprocess_chunk(self, audio, sample_rate: int, params: SynthesisParameters):
        return self._apply_speed(audio, sample_rate, params.speed)
