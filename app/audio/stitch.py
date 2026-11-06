"""
Chunk stitching: sentence pauses and edge fades that join rendered chunks
into one continuous waveform.
"""

from __future__ import annotations

import numpy as np


def prepare_chunk(
    chunk: np.ndarray,
    is_first: bool,
    sample_rate: int,
    pause_ms: int = 250,
    crossfade_ms: int = 40,
) -> np.ndarray:
    """Prepares one rendered chunk: an optional leading sentence pause plus
    short edge fades that remove clicks at chunk boundaries."""
    cur = np.asarray(chunk, dtype=np.float32).reshape(-1)
    if cur.size == 0:
        return np.zeros(0, dtype=np.float32)

    pause_samples = int((pause_ms / 1000.0) * sample_rate)
    crossfade_samples = int((crossfade_ms / 1000.0) * sample_rate)

    if crossfade_samples > 0 and len(cur) > crossfade_samples * 2:
        fade_in = np.linspace(0.0, 1.0, crossfade_samples, dtype=np.float32)
        fade_out = np.linspace(1.0, 0.0, crossfade_samples, dtype=np.float32)
        cur = cur.copy()
        cur[:crossfade_samples] *= fade_in
        cur[-crossfade_samples:] *= fade_out

    if is_first or pause_samples <= 0:
        return cur.astype(np.float32)

    pause_silence = np.zeros(pause_samples, dtype=np.float32)
    return np.concatenate([pause_silence, cur]).astype(np.float32)


def stitch_chunks(
    chunks: list[np.ndarray],
    sample_rate: int,
    pause_ms: int = 250,
    crossfade_ms: int = 40,
) -> np.ndarray:
    """Stitches rendered chunks into one waveform with pauses and edge fades."""
    prepared: list[np.ndarray] = []
    for chunk in chunks:
        if len(chunk) == 0:
            continue
        prepared.append(
            prepare_chunk(
                chunk,
                is_first=not prepared,
                sample_rate=sample_rate,
                pause_ms=pause_ms,
                crossfade_ms=crossfade_ms,
            )
        )
    if not prepared:
        return np.zeros(0, dtype=np.float32)
    return np.concatenate(prepared).astype(np.float32)
