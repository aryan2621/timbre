from __future__ import annotations

import io
import json
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import soundfile as sf

from app.core.config import config_manager
from app.core.logging_setup import get_logger
from app.data.model_catalog import get_model, is_model_present, model_local_path
from app.engines.base import EngineLicense, ParamSpec, SynthesisParameters, TTSEngine
from app.runtimes.native import NativeServer

logger = get_logger("mlx_audio")

# One bundled mlx-audio server (its own Python environment, Apple Silicon only) serves every
# engine below, so their dependency pins never meet the ones in this process.
SERVER = NativeServer("mlx-audio-server", "MLX voice", ready_path="/v1/models")


@dataclass(frozen=True)
class MlxVoiceSpec:
    model_id: str
    name: str
    license: EngineLicense
    languages: tuple[str, ...] = ("en",)
    sample_rate: int = 24000
    uses_ref_text: bool = False  # cloning is closer when the clip's transcript is passed along
    preset_voices: tuple[str, ...] = ()  # fixed voices; alone they replace the reference clip
    can_clone: bool = False  # with preset voices: the reference clip stays an option
    controls: tuple[ParamSpec, ...] = ()


KOKORO_VOICES = (
    "af_heart", "af_bella", "af_nicole", "af_sarah", "af_sky",
    "am_adam", "am_michael", "bf_emma", "bf_isabella", "bm_george",
)

def _qwen(size: str, memory_note: str) -> MlxVoiceSpec:
    return MlxVoiceSpec(
        model_id=f"qwen3-tts-{size.lower()}",
        name=f"Qwen3-TTS {size}",
        license=EngineLicense(
            name="Apache-2.0",
            url="https://huggingface.co/Qwen/Qwen3-TTS-12Hz-" + size + "-Base",
            commercial_permitted=True,
            notice=f"Qwen3-TTS {size} Base by Alibaba Qwen, run through MLX. {memory_note}",
        ),
        languages=("en", "zh", "ja", "ko", "de", "fr", "ru", "pt", "es", "it"),
        uses_ref_text=True,
    )


ZONOS3_VOICES = (
    "jett", "savannah", "wyatt", "imogen", "rupert", "cillian", "thaddeus", "willow", "morgana", "sakura",
    "haoran", "meilin", "ananya", "arjun", "chaitanya", "gaspard", "ginevra", "leonor", "liesel", "lorenzo",
    "minjun", "rodrigo", "seoyeon", "sravya", "thiago", "wolfgang", "ximena",
)
FROM_CLIP = "reference clip"

SPECS = (
    MlxVoiceSpec(
        model_id="kokoro-82m",
        name="Kokoro",
        license=EngineLicense(
            name="Apache-2.0",
            url="https://huggingface.co/hexgrad/Kokoro-82M",
            commercial_permitted=True,
            notice="Kokoro-82M by hexgrad, run through MLX. Fixed voices, no cloning. English only here.",
        ),
        preset_voices=KOKORO_VOICES,
    ),
    MlxVoiceSpec(
        model_id="zonos3-mini",
        name="ZONOS3 Mini",
        license=EngineLicense(
            name="Apache-2.0",
            url="https://huggingface.co/Zyphra/ZONOS3-Mini",
            commercial_permitted=True,
            notice="ZONOS3-Mini by Zyphra, run through MLX. 27 built-in voices or a cloned clip, no transcript needed.",
        ),
        languages=("en", "zh", "de", "es", "fr", "hi", "it", "ko", "pt", "te"),
        sample_rate=44100,
        preset_voices=ZONOS3_VOICES,
        can_clone=True,
    ),
    _qwen("1.7B", "Best quality, about 4 GB of weights."),
    _qwen("0.6B", "Lighter and faster."),
)


def reference_transcript(clip: str | Path) -> str:
    """Transcript of a reference clip, cached beside it as <clip>.txt; empty when no Whisper model works."""
    cache = Path(f"{clip}.txt")
    try:
        if cache.is_file():
            return cache.read_text().strip()
        from app.services.agent_service import transcribe

        text = transcribe(Path(clip).read_bytes())
        cache.write_text(text)
        return text
    except Exception as exc:  # noqa: BLE001 - cloning still works without a transcript
        logger.warning("No transcript for %s: %s", clip, exc)
        return ""


class MlxAudioEngine(TTSEngine):
    def __init__(self, spec: MlxVoiceSpec) -> None:
        self.spec = spec
        self.model_id = spec.model_id
        voices = (FROM_CLIP, *spec.preset_voices) if spec.can_clone else spec.preset_voices
        self.controls = (
            *(
                [ParamSpec("voice", "Voice", kind="select", options=voices, default=voices[0], group="style")]
                if voices
                else []
            ),
            *spec.controls,
            ParamSpec("speed", "Speed", 0.5, 2.0, 0.05, 1.0, group="delivery"),
        )

    @property
    def name(self) -> str:
        return self.spec.name

    @property
    def license_info(self) -> EngineLicense:
        return self.spec.license

    @property
    def supported_languages(self) -> list[str]:
        return list(self.spec.languages)

    @property
    def requires_gpu_recommended(self) -> bool:
        return True

    @property
    def native_sample_rate(self) -> int:
        return self.spec.sample_rate

    def _weights_present(self) -> bool:
        model = get_model(self.spec.model_id)
        return model is not None and is_model_present(model, config_manager.get_models_directory())

    def unavailable_reason(self) -> str | None:
        if not SERVER.is_available():
            return "Install the Apple Silicon voice engine from the Models page first (Apple Silicon only)."
        if not self._weights_present():
            return f"Download {self.spec.name} from the Models page first"
        return None

    def is_available(self) -> bool:
        return self.unavailable_reason() is None

    def is_loaded(self) -> bool:
        return SERVER.is_running()

    def get_default_params(self) -> SynthesisParameters:
        return SynthesisParameters(speed=1.0, language=self.spec.languages[0], enable_watermark=False)

    def load_model(self, progress_callback: Callable[[float, str], None] | None = None) -> bool:
        if not self.is_available():
            return False
        if progress_callback:
            progress_callback(30.0, f"Starting {self.spec.name}")
        SERVER.ensure([])
        return True

    def unload_model(self) -> None:
        SERVER.stop()  # the weights live in that process, so stopping it frees them

    def _request_body(self, text: str, reference_audio_path: str | Path, params: SynthesisParameters) -> dict:
        model = get_model(self.spec.model_id)
        assert model is not None, self.spec.model_id
        body: dict = {
            "model": str(model_local_path(model, config_manager.get_models_directory())),
            "input": text,
            "speed": params.speed,
            "response_format": "wav",
        }
        voice = str(params.extra.get("voice") or (FROM_CLIP if self.spec.can_clone else ""))
        if self.spec.preset_voices and voice != FROM_CLIP:
            body["voice"] = voice or self.spec.preset_voices[0]
            if not self.spec.can_clone:
                body["lang_code"] = body["voice"][0]  # kokoro: a = American, b = British
        elif reference_audio_path:
            body["ref_audio"] = str(reference_audio_path)
            body["lang_code"] = params.language
            if self.spec.uses_ref_text and (transcript := reference_transcript(reference_audio_path)):
                body["ref_text"] = transcript
        return body

    def clone_and_synthesize(
        self, text: str, reference_audio_path: str | Path, params: SynthesisParameters
    ) -> tuple[np.ndarray, int]:
        if not SERVER.is_running() and not self.load_model():
            raise RuntimeError(self.unavailable_reason() or f"{self.spec.name} could not start. See mlx-audio-server.log.")
        body = self._request_body(text, reference_audio_path, params)
        request = urllib.request.Request(
            SERVER.url + "/v1/audio/speech",
            data=json.dumps(body).encode(),
            headers={"Content-Type": "application/json"},
        )
        data = SERVER.read(request)
        if not data:
            raise RuntimeError(f"{self.spec.name} returned no audio. See mlx-audio-server.log.")
        audio, rate = sf.read(io.BytesIO(data), dtype="float32")
        if audio.ndim > 1:
            audio = audio.mean(axis=1)
        return np.ascontiguousarray(audio, dtype=np.float32), int(rate)
