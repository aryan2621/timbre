"""
Sentence-aware text chunker with speech duration estimation and punctuation handling.
"""

from __future__ import annotations

import re
from typing import List, Tuple


class TextChunker:
    """Splits long text passages into natural linguistic chunks for TTS synthesis."""

    # Common English abbreviations that should not trigger sentence breaks
    ABBREVIATIONS = {
        "mr", "mrs", "ms", "dr", "prof", "sr", "jr", "vs", "etc", "fig", "e.g", "i.e",
        "inc", "ltd", "co", "corp", "u.s", "u.k", "jan", "feb", "mar", "apr", "aug",
        "sept", "oct", "nov", "dec",
    }

    # Average speaking rate: ~150 words per minute (~2.5 words / second)
    WORDS_PER_MINUTE: float = 150.0

    @classmethod
    def estimate_duration_seconds(cls, text: str, speed_multiplier: float = 1.0) -> float:
        """Estimates spoken audio duration in seconds based on word count and speed."""
        words = len(text.strip().split())
        if words == 0:
            return 0.0
        base_seconds = (words / cls.WORDS_PER_MINUTE) * 60.0
        return max(0.5, base_seconds / max(0.1, speed_multiplier))

    @classmethod
    def count_metrics(cls, text: str) -> Tuple[int, int]:
        """Returns (character_count, word_count) for the input text."""
        stripped = text.strip()
        char_count = len(stripped)
        word_count = len(stripped.split()) if stripped else 0
        return char_count, word_count

    @classmethod
    def split_into_sentences(cls, text: str) -> List[str]:
        """
        Splits text into sentences based on punctuation while respecting common abbreviations.
        """
        cleaned = text.strip()
        if not cleaned:
            return []

        # Split across paragraphs or line breaks first
        paragraphs = [p.strip() for p in re.split(r"\n+", cleaned) if p.strip()]
        sentences: List[str] = []

        for p in paragraphs:
            # Tokenize by punctuation (? ! .) followed by whitespace or quotes
            raw_splits = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9\"'‘“])", p)
            buffer = ""

            for part in raw_splits:
                if not part:
                    continue
                if buffer:
                    # Check if the split was on an abbreviation
                    last_word = buffer.rstrip(".!?").split()[-1].lower() if buffer.split() else ""
                    if last_word in cls.ABBREVIATIONS:
                        buffer += " " + part
                        continue
                    else:
                        sentences.append(buffer.strip())
                        buffer = part
                else:
                    buffer = part

            if buffer:
                sentences.append(buffer.strip())

        return sentences

    @classmethod
    def chunk_text(
        cls,
        text: str,
        max_chars_per_chunk: int = 240,
        min_chars_per_chunk: int = 30,
    ) -> List[str]:
        """
        Groups sentences into coherent chunks that fit comfortably within engine limits.
        If a single sentence exceeds max_chars_per_chunk, it is split by secondary punctuation
        (commas, colons, dashes).
        """
        sentences = cls.split_into_sentences(text)
        if not sentences:
            return []

        chunks: List[str] = []
        current_chunk = ""

        for sentence in sentences:
            # If the single sentence is longer than max limit, split by sub-clauses
            if len(sentence) > max_chars_per_chunk:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                    current_chunk = ""

                sub_chunks = cls._split_long_sentence(sentence, max_chars_per_chunk)
                chunks.extend(sub_chunks)
                continue

            # If adding this sentence exceeds limit, finalize current chunk
            if current_chunk and (len(current_chunk) + len(sentence) + 1 > max_chars_per_chunk):
                chunks.append(current_chunk.strip())
                current_chunk = sentence
            else:
                if current_chunk:
                    current_chunk += " " + sentence
                else:
                    current_chunk = sentence

        if current_chunk:
            chunks.append(current_chunk.strip())

        return chunks

    @classmethod
    def _split_long_sentence(cls, sentence: str, max_chars: int) -> List[str]:
        """Splits an overly long single sentence by semicolons, colons, commas, or words."""
        clause_parts = re.split(r"([,;:\—\–\-])", sentence)
        sub_chunks: List[str] = []
        buf = ""

        for part in clause_parts:
            if len(buf) + len(part) <= max_chars:
                buf += part
            else:
                if buf.strip():
                    sub_chunks.append(buf.strip())
                # If a single part is still huge (e.g. no punctuation), split by words
                if len(part) > max_chars:
                    words = part.split()
                    w_buf = ""
                    for w in words:
                        if len(w_buf) + len(w) + 1 <= max_chars:
                            w_buf = f"{w_buf} {w}".strip()
                        else:
                            if w_buf:
                                sub_chunks.append(w_buf)
                            w_buf = w
                    buf = w_buf
                else:
                    buf = part

        if buf.strip():
            sub_chunks.append(buf.strip())

        return sub_chunks

