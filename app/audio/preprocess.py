"""
Audio preprocessing pipeline: mono conversion, resampling, noise reduction,
silence trimming (VAD), and EBU R128 (-23 LUFS) loudness normalization.
"""

from __future__ import annotations

import math

try:
    import numpy as np
except ImportError:  # pragma: no cover - numpy is a hard requirement in practice
    np = None  # type: ignore[assignment]

from app.core.logging_setup import get_logger

logger = get_logger("preprocess")


class AudioPreprocessor:
    """Preprocesses raw audio into clean, normalized reference clips for TTS engines."""

    @staticmethod
    def to_mono(audio: np.ndarray) -> np.ndarray:
        """Converts multi-channel audio to single-channel mono."""
        if audio.ndim == 1:
            return audio
        if audio.ndim == 2:
            # Average stereo or surround channels to mono
            return np.mean(audio, axis=-1)
        raise ValueError(f"Unsupported audio array dimension: {audio.ndim}")

    @staticmethod
    def resample(audio: np.ndarray, orig_sr: int, target_sr: int) -> np.ndarray:
        """Resamples audio from orig_sr to target_sr using librosa or polyphase interpolation."""
        if orig_sr == target_sr:
            return audio

        try:
            import librosa  # type: ignore
            resampled = librosa.resample(audio, orig_sr=orig_sr, target_sr=target_sr)
            return resampled.astype(np.float32)
        except ImportError:
            # Fallback linear/polyphase resampler if librosa is not yet installed
            duration = len(audio) / orig_sr
            num_target_samples = int(round(duration * target_sr))
            indices = np.linspace(0, len(audio) - 1, num_target_samples)
            resampled = np.interp(indices, np.arange(len(audio)), audio)
            return resampled.astype(np.float32)

    @staticmethod
    def denoise(audio: np.ndarray, sample_rate: int) -> np.ndarray:
        """Reduces stationary noise using spectral gating (noisereduce) or frequency filter."""
        try:
            import noisereduce as nr  # type: ignore
            # Stationary spectral gating
            cleaned = nr.reduce_noise(
                y=audio,
                sr=sample_rate,
                prop_decrease=0.75,
                stationary=True,
            )
            return cleaned.astype(np.float32)
        except Exception as e:
            logger.debug("noisereduce not available or failed (%s). Applying high-pass rumble filter.", e)
            # Gentle high-pass filter to strip subsonic rumble (< 60Hz)
            return AudioPreprocessor._highpass_filter(audio, sample_rate, cutoff=60.0)

    @staticmethod
    def trim_silence_vad(
        audio: np.ndarray,
        sample_rate: int,
        threshold_db: float = -40.0,
        padding_ms: int = 100,
    ) -> np.ndarray:
        """
        Trims leading and trailing silence and strips internal dead-air pauses.
        Uses energy-based VAD with a threshold relative to peak dBFS.
        """
        if len(audio) == 0:
            return audio

        abs_audio = np.abs(audio)
        peak = np.max(abs_audio)
        if peak < 1e-6:
            return audio  # Completely silent

        # Frame-based energy computation
        frame_len = int(sample_rate * 0.02)  # 20ms frames
        if frame_len == 0 or len(audio) < frame_len:
            return audio

        num_frames = len(audio) // frame_len
        energies = []
        for i in range(num_frames):
            frame = audio[i * frame_len : (i + 1) * frame_len]
            rms = np.sqrt(np.mean(frame**2) + 1e-12)
            db = 20 * math.log10(max(rms, 1e-9))
            energies.append(db)

        peak_db = 20 * math.log10(max(peak, 1e-9))
        cutoff_db = peak_db + threshold_db

        voiced_mask = [e > cutoff_db for e in energies]
        if not any(voiced_mask):
            return audio

        # Find first and last voiced frames
        first_voiced = next(i for i, v in enumerate(voiced_mask) if v)
        last_voiced = len(voiced_mask) - 1 - next(i for i, v in enumerate(reversed(voiced_mask)) if v)

        padding_frames = int((padding_ms / 1000.0) / 0.02)
        start_idx = max(0, (first_voiced - padding_frames) * frame_len)
        end_idx = min(len(audio), (last_voiced + 1 + padding_frames) * frame_len)

        return audio[start_idx:end_idx]

    @staticmethod
    def normalize_loudness(
        audio: np.ndarray,
        sample_rate: int,
        target_lufs: float = -23.0,
    ) -> np.ndarray:
        """
        Normalizes audio to target LUFS using pyloudnorm (ITU-R BS.1770-4 standard).
        Falls back to peak normalization (-1.0 dBFS) if pyloudnorm is unavailable.
        """
        if len(audio) == 0:
            return audio

        try:
            import pyloudnorm as pyln  # type: ignore

            meter = pyln.Meter(sample_rate)
            loudness = meter.integrated_loudness(audio)

            if not np.isneginf(loudness) and not np.isnan(loudness):
                normalized = pyln.normalize.loudness(audio, loudness, target_lufs)
                # Clip guard to prevent digital clipping
                peak = np.max(np.abs(normalized))
                if peak > 0.98:
                    normalized = (normalized / peak) * 0.98
                return normalized.astype(np.float32)
        except Exception as e:
            logger.debug("pyloudnorm normalization fell back to peak normalization: %s", e)

        # Fallback: Peak normalization to -1 dBFS (0.891)
        peak = np.max(np.abs(audio))
        if peak > 1e-6:
            target_peak = 10 ** (-1.0 / 20.0)  # ~0.891
            return (audio * (target_peak / peak)).astype(np.float32)
        return audio

    @classmethod
    def process_reference_audio(
        cls,
        audio: np.ndarray,
        orig_sr: int,
        target_sr: int = 24000,
        apply_denoise: bool = True,
        apply_vad: bool = True,
        apply_normalize: bool = True,
    ) -> tuple[np.ndarray, int]:
        """Runs the complete reference audio preprocessing pipeline."""
        # 1. Convert to mono
        mono = cls.to_mono(audio)

        # 2. Resample
        resampled = cls.resample(mono, orig_sr, target_sr)

        # 3. Denoise
        cleaned = cls.denoise(resampled, target_sr) if apply_denoise else resampled

        # 4. Silence Trimming
        trimmed = cls.trim_silence_vad(cleaned, target_sr) if apply_vad else cleaned

        # 5. Loudness Normalization (-23 LUFS)
        normalized = cls.normalize_loudness(trimmed, target_sr, -23.0) if apply_normalize else trimmed

        return normalized.astype(np.float32), target_sr

    @staticmethod
    def _highpass_filter(audio: np.ndarray, sample_rate: int, cutoff: float = 60.0) -> np.ndarray:
        """Simple single-pole high-pass IIR filter for removing subsonic DC and rumble."""
        rc = 1.0 / (2.0 * math.pi * cutoff)
        dt = 1.0 / sample_rate
        alpha = rc / (rc + dt)
        out = np.zeros_like(audio)
        for i in range(1, len(audio)):
            out[i] = alpha * (out[i - 1] + audio[i] - audio[i - 1])
        return out
