"""
Audio handling utilities: preprocessing, quality checking, text chunking, recording, playback, and export.
"""

from app.audio.chunker import TextChunker

# Optional imports for environments where numpy / soundfile are installed
try:
    from app.audio.export import AudioExporter
    from app.audio.player import AudioPlayer, PlaybackState
    from app.audio.preprocess import AudioPreprocessor
    from app.audio.quality import AudioQualityChecker
    from app.audio.recorder import AudioRecorder
    __all__ = [
        "TextChunker",
        "AudioPreprocessor",
        "AudioQualityChecker",
        "AudioRecorder",
        "AudioPlayer",
        "PlaybackState",
        "AudioExporter",
    ]
except ImportError:
    __all__ = ["TextChunker"]
