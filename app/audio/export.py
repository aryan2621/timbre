"""
Multi-format audio exporter (WAV, MP3, FLAC, OGG) with bit-depth selection
and ethical metadata tagging ('AI-generated voice').
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, Optional

try:
    import numpy as np
except ImportError:
    np = None

from app.audio.preprocess import AudioPreprocessor
from app.core.logging_setup import get_logger

logger = get_logger("export")


class AudioExporter:
    """Exports audio waveforms to various formats with safety metadata tags."""

    SUPPORTED_FORMATS = ["wav", "mp3", "flac", "ogg"]
    SUPPORTED_BIT_DEPTHS = [16, 24, 32]

    @classmethod
    def export(
        cls,
        audio: np.ndarray,
        sample_rate: int,
        output_path: Path,
        format_str: str = "wav",
        target_sample_rate: Optional[int] = None,
        bit_depth: int = 16,
        metadata: Optional[Dict[str, str]] = None,
    ) -> bool:
        """
        Exports numpy audio array to designated file format on disk.
        Injects AI-generated voice identification metadata.
        """
        fmt = format_str.lower().strip()
        if fmt not in cls.SUPPORTED_FORMATS:
            raise ValueError(f"Unsupported format '{fmt}'. Choose from {cls.SUPPORTED_FORMATS}")

        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Resample if requested
        export_sr = sample_rate
        export_audio = audio
        if target_sample_rate and target_sample_rate != sample_rate:
            export_audio = AudioPreprocessor.resample(audio, sample_rate, target_sample_rate)
            export_sr = target_sample_rate

        # Standard safety metadata
        meta = {
            "title": "VoiceClone Synthesis",
            "artist": "VoiceClone Studio",
            "comment": "AI-generated voice / Zero-shot neural synthesis",
            "encoder": "VoiceClone Studio Audio Engine",
        }
        if metadata:
            meta.update(metadata)

        # WAV / FLAC export via soundfile
        if fmt in ["wav", "flac"]:
            return cls._export_soundfile(export_audio, export_sr, output_path, fmt, bit_depth)

        # MP3 / OGG export via pydub / soundfile
        return cls._export_compressed(export_audio, export_sr, output_path, fmt, bit_depth, meta)

    @classmethod
    def _export_soundfile(
        cls,
        audio: np.ndarray,
        sample_rate: int,
        output_path: Path,
        fmt: str,
        bit_depth: int,
    ) -> bool:
        try:
            import soundfile as sf  # type: ignore

            subtype_map = {
                16: "PCM_16",
                24: "PCM_24",
                32: "FLOAT" if fmt == "wav" else "PCM_24",
            }
            subtype = subtype_map.get(bit_depth, "PCM_16")

            sf.write(
                str(output_path),
                audio,
                sample_rate,
                format=fmt.upper(),
                subtype=subtype,
            )
            logger.info("Exported audio to %s (%s, %d-bit, %d Hz)", output_path, fmt, bit_depth, sample_rate)
            return True
        except Exception as e:
            logger.error("Soundfile export failed for %s: %s", output_path, e)
            return False

    @classmethod
    def _export_compressed(
        cls,
        audio: np.ndarray,
        sample_rate: int,
        output_path: Path,
        fmt: str,
        bit_depth: int,
        metadata: Dict[str, str],
    ) -> bool:
        """Exports compressed audio (MP3, OGG) using soundfile (for OGG) or pydub + ffmpeg (for MP3)."""
        if fmt == "ogg":
            try:
                import soundfile as sf  # type: ignore
                sf.write(str(output_path), audio, sample_rate, format="OGG")
                logger.info("Exported OGG audio to %s", output_path)
                return True
            except Exception as e:
                logger.debug("soundfile OGG write failed (%s), attempting pydub fallback.", e)

        # MP3 / fallback using pydub
        try:
            from pydub import AudioSegment  # type: ignore

            # Convert float32 [-1.0, 1.0] to int16 PCM bytes
            clipped = np.clip(audio, -1.0, 1.0)
            int16_data = (clipped * 32767).astype(np.int16)
            raw_bytes = int16_data.tobytes()

            segment = AudioSegment(
                data=raw_bytes,
                sample_width=2,
                frame_rate=sample_rate,
                channels=1,
            )

            # Export with tags
            tags = {
                "artist": metadata.get("artist", "VoiceClone Studio"),
                "comment": metadata.get("comment", "AI-generated voice"),
                "title": metadata.get("title", "VoiceClone"),
            }
            segment.export(
                str(output_path),
                format=fmt,
                bitrate="192k",
                tags=tags,
            )
            logger.info("Exported %s audio via pydub to %s", fmt, output_path)
            return True
        except Exception as e:
            logger.error(
                "Compressed export failed for %s (check if ffmpeg is installed): %s",
                output_path,
                e,
            )
            return False  # never report success for a file that was not written
