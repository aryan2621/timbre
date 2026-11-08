"""
Abstract base class and parameter contracts for all pluggable zero-shot TTS engines.
"""

from __future__ import annotations

import threading
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    import numpy as np
except ImportError:  # pragma: no cover - numpy is a hard requirement in practice
    np = None  # type: ignore[assignment]


@dataclass
class ParamSpec:
    key: str
    label: str
    min: float = 0.0
    max: float = 1.0
    step: float = 0.1
    default: float | str = 0.0
    kind: str = "number"
    options: tuple[str, ...] = ()
    description: str = ""
    group: str = "style"


@dataclass
class EngineLicense:
    """Legal license information associated with a TTS model and its weights."""

    name: str  # e.g. "MIT", "CPML (Coqui Public Model License)", "Apache-2.0"
    url: str
    commercial_permitted: bool
    notice: str


@dataclass
class SynthesisParameters:
    """Standardized hyperparameter controls passed to cloning engines."""

    temperature: float = 0.75
    cfg_weight: float = 2.5
    exaggeration: float = 1.0  # Emotional / pitch variance
    speed: float = 1.0
    seed: int = -1  # -1 for non-deterministic random
    top_p: float = 0.85
    repetition_penalty: float = 2.0
    language: str = "en"
    enable_watermark: bool = True
    extra: dict[str, Any] = field(default_factory=dict)


class Engine(ABC):
    """Lifecycle and metadata shared by every pluggable model engine (speech or sound)."""

    # Shared by all engines: callers hold it around load/unload/synthesize so a worker thread,
    # the idle-unload timer and the registry never touch model weights concurrently.
    # Each engine subclass gets its own lock (``__init_subclass__``) so a render on one
    # engine never blocks a render on another.
    lock = threading.RLock()

    # Catalog id of this engine's downloadable weights (app/data/model_catalog.py), if any.
    model_id: str | None = None

    controls: tuple[ParamSpec, ...] = ()

    def unavailable_reason(self) -> str | None:
        """None when the engine can run here, otherwise a short reason why not."""
        if not self.is_available():
            return "Its Python package is not installed in the API environment"
        return None

    def __init_subclass__(cls, **kwargs: Any) -> None:
        super().__init_subclass__(**kwargs)
        cls.lock = threading.RLock()

    @property
    @abstractmethod
    def name(self) -> str:
        """Display name of the engine."""
        pass

    @property
    @abstractmethod
    def license_info(self) -> EngineLicense:
        """License terms and commercial usability status."""
        pass

    @property
    @abstractmethod
    def requires_gpu_recommended(self) -> bool:
        """Whether a dedicated GPU (CUDA/MPS) is strongly recommended for practical synthesis."""
        pass

    @property
    @abstractmethod
    def native_sample_rate(self) -> int:
        """The native output sample rate produced by this engine."""
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """Checks if model weights are present on disk and ready to be loaded."""
        pass

    @abstractmethod
    def is_loaded(self) -> bool:
        """Returns True if model weights are currently resident in RAM/VRAM."""
        pass

    @abstractmethod
    def load_model(self, progress_callback: Callable[[float, str], None] | None = None) -> bool:
        """
        Loads the model weights into device memory.
        progress_callback receives (percent_0_to_100, status_message).
        """
        pass

    @abstractmethod
    def unload_model(self) -> None:
        """Frees model weights from RAM/VRAM and clears PyTorch device cache."""
        pass


class TTSEngine(Engine):
    """Abstract interface that every speech synthesis and cloning engine must implement."""

    @property
    @abstractmethod
    def supported_languages(self) -> list[str]:
        """List of ISO language codes supported by this engine."""
        pass

    @abstractmethod
    def clone_and_synthesize(
        self,
        text: str,
        reference_audio_path: str | Path,
        params: SynthesisParameters,
    ) -> tuple[np.ndarray, int]:
        """
        Synthesizes speech for the provided text in the voice of the reference audio.
        Returns:
            Tuple[np.ndarray, int]: (audio_samples_float32, sample_rate)
        """
        pass

    def synthesize_chunk(
        self,
        text: str,
        reference_audio_path: str | Path,
        params: SynthesisParameters,
    ) -> tuple[np.ndarray, int]:
        """
        Synthesizes a single text chunk for streaming playback.

        The default implementation simply delegates to
        :meth:`clone_and_synthesize`. Engines with a native streaming API can
        override it to hand back audio sooner. Conditionals (reference-voice
        encoding) should be cached per voice so repeated chunks stay cheap.
        Returns:
            Tuple[np.ndarray, int]: (audio_samples_float32, sample_rate)
        """
        return self.clone_and_synthesize(text, reference_audio_path, params)

    def postprocess_chunk(
        self, audio: np.ndarray, sample_rate: int, params: SynthesisParameters
    ) -> np.ndarray:
        """CPU-side work on a rendered chunk (e.g. time-stretch).

        The render loop runs this on a worker thread while the next chunk is
        being generated, so it must not touch the model. Default: no-op.
        """
        return audio

    @abstractmethod
    def get_default_params(self) -> SynthesisParameters:
        """Returns the recommended default parameters tuned for this engine."""
        pass


@dataclass
class SoundParameters:
    duration_seconds: float = 10.0
    steps: int = 100
    guidance: float = 7.0
    seed: int = -1
    negative_prompt: str = ""
    lyrics: str = ""
    extra: dict[str, Any] = field(default_factory=dict)


class SoundEngine(Engine):
    max_duration_seconds: float = 30.0
    kinds: tuple[str, ...] = ("sfx", "music")
    supports_lyrics: bool = False
    supports_negative_prompt: bool = True

    @abstractmethod
    def generate(
        self,
        prompt: str,
        params: SoundParameters,
        on_step: Callable[[int, int], None] | None = None,
    ) -> tuple[np.ndarray, int]:
        pass

    @abstractmethod
    def get_default_params(self) -> SoundParameters:
        pass
