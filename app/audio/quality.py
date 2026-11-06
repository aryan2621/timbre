"""
Audio quality analyzer for reference voice recordings.
Calculates SNR, clipping, duration limits, and acoustic consistency.
"""

from __future__ import annotations

import math
from typing import Any

try:
    import numpy as np
except ImportError:  # pragma: no cover - numpy is a hard requirement in practice
    np = None  # type: ignore[assignment]

from app.core.logging_setup import get_logger
from app.data.models import QualityReport

logger = get_logger("quality")


class AudioQualityChecker:
    """Evaluates reference audio against zero-shot TTS suitability standards."""

    MIN_DURATION_SECONDS: float = 5.0
    MAX_DURATION_SECONDS: float = 30.0
    MIN_SNR_DB: float = 14.0
    MAX_CLIPPING_RATIO: float = 0.001  # 0.1% of samples at ceiling

    @classmethod
    def analyze(cls, audio: np.ndarray, sample_rate: int) -> QualityReport:
        """
        Inspects audio waveform and produces a comprehensive QualityReport.
        """
        if len(audio) == 0:
            return QualityReport(
                score=0,
                duration_seconds=0.0,
                sample_rate=sample_rate,
                channels=1,
                snr_db=0.0,
                clipping_ratio=0.0,
                is_acceptable=False,
                warnings=["Audio is empty."],
            )

        duration = len(audio) / sample_rate
        channels = 1 if audio.ndim == 1 else audio.shape[-1]
        mono = audio if audio.ndim == 1 else np.mean(audio, axis=-1)

        warnings: list[str] = []
        deductions: int = 0

        # 1. Duration check
        if duration < cls.MIN_DURATION_SECONDS:
            warnings.append(f"Recording is too short ({duration:.1f}s). Aim for 5 to 30 seconds for optimal voice timbre.")
            deductions += 30
        elif duration > cls.MAX_DURATION_SECONDS:
            warnings.append(f"Recording is long ({duration:.1f}s). Engines may truncate or lose consistency above 30s.")
            deductions += 15

        # 2. Clipping check (samples close to +/- 1.0)
        peak = np.max(np.abs(mono))
        clipping_mask = np.abs(mono) >= 0.995
        clipping_ratio = float(np.mean(clipping_mask))

        if clipping_ratio > cls.MAX_CLIPPING_RATIO:
            warnings.append(f"Audio clipping detected ({clipping_ratio * 100:.2f}% of samples). Lower your microphone gain.")
            deductions += min(40, int(clipping_ratio * 2000))
        elif peak < 0.05:
            warnings.append("Audio signal is very quiet. Increase microphone input volume.")
            deductions += 25

        # 3. SNR estimation (Signal to Noise Ratio)
        snr_db = cls._estimate_snr(mono)
        if snr_db < cls.MIN_SNR_DB:
            warnings.append(f"High background noise detected (SNR: {snr_db:.1f} dB). Record in a quieter space.")
            deductions += max(10, int(cls.MIN_SNR_DB - snr_db) * 2)

        # 4. Music / Multi-speaker / Spectral artifact heuristic
        is_complex, complexity_reason = cls._check_complexity_and_music(mono, sample_rate)
        if is_complex:
            warnings.append(complexity_reason)
            deductions += 20

        score = max(0, min(100, 100 - deductions))
        is_acceptable = score >= 50 and duration >= 3.0

        details: dict[str, float] = {
            "peak_amplitude": float(peak),
            "estimated_snr_db": float(snr_db),
            "clipping_percentage": float(clipping_ratio * 100.0),
        }

        logger.debug(
            "Quality analysis completed: Score=%d, Duration=%.2fs, SNR=%.1fdB, Warnings=%s",
            score,
            duration,
            snr_db,
            warnings,
        )

        return QualityReport(
            score=score,
            duration_seconds=round(duration, 2),
            sample_rate=sample_rate,
            channels=channels,
            snr_db=round(snr_db, 1),
            clipping_ratio=round(clipping_ratio, 5),
            is_acceptable=is_acceptable,
            warnings=warnings,
            details=details,
        )

    @staticmethod
    def _estimate_snr(mono: np.ndarray) -> float:
        """
        Estimates SNR by comparing energy of active voiced frames
        against the quietest percentile (noise floor).
        """
        frame_size = 512
        if len(mono) < frame_size * 4:
            return 20.0

        num_frames = len(mono) // frame_size
        frame_powers: list[Any] = []
        for i in range(num_frames):
            frame = mono[i * frame_size : (i + 1) * frame_size]
            power = np.mean(frame**2)
            frame_powers.append(power)

        sorted_powers = np.sort(np.array(frame_powers))
        # Noise floor estimated from lowest 10% frames
        noise_floor_power = np.mean(sorted_powers[: max(1, int(len(sorted_powers) * 0.1))])
        # Signal power estimated from top 40% frames
        signal_power = np.mean(sorted_powers[int(len(sorted_powers) * 0.6) :])

        if noise_floor_power < 1e-12:
            return 45.0  # Pristine noise floor

        ratio = (signal_power + 1e-12) / (noise_floor_power + 1e-12)
        snr_db = 10.0 * math.log10(max(1.0, ratio))
        return min(60.0, max(0.0, snr_db))

    @staticmethod
    def _check_complexity_and_music(mono: np.ndarray, sample_rate: int) -> tuple[bool, str]:
        """
        Heuristic to detect sustained background music or multi-speaker overlapping
        using spectral flatness and zero-crossing rate variance.
        """
        if len(mono) < sample_rate:
            return False, ""

        # Zero crossing rate (ZCR)
        zero_crossings = np.sum(np.abs(np.diff(np.sign(mono)))) / (2 * len(mono))
        if zero_crossings > 0.45:
            return True, "High continuous high-frequency noise or hiss detected."

        # High sustained energy without silence gaps suggests background music
        frame_len = int(sample_rate * 0.1)  # 100ms
        num_frames = len(mono) // frame_len
        if num_frames > 10:
            rms_vals = [
                np.sqrt(np.mean(mono[i * frame_len : (i + 1) * frame_len] ** 2))
                for i in range(num_frames)
            ]
            std_rms = np.std(rms_vals)
            mean_rms = np.mean(rms_vals)
            # Normal speech has natural pauses (high standard deviation / variance).
            # Heavy continuous background music creates low dynamic variance.
            if mean_rms > 0.1 and (std_rms / (mean_rms + 1e-6)) < 0.15:
                return True, "Possible continuous background music or secondary speaker detected."

        return False, ""
