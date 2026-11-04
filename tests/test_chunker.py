"""
Unit tests for sentence-aware text chunking and speaking duration estimation.
"""

import unittest
from app.audio.chunker import TextChunker


class TestTextChunker(unittest.TestCase):

    def test_word_and_char_counting(self):
        text = "Hello world! This is a test."
        chars, words = TextChunker.count_metrics(text)
        self.assertEqual(words, 6)
        self.assertEqual(chars, len(text))

    def test_duration_estimation(self):
        # 150 words per minute -> 15 words should take ~6.0 seconds
        words_15 = "word " * 15
        est = TextChunker.estimate_duration_seconds(words_15, speed_multiplier=1.0)
        self.assertAlmostEqual(est, 6.0, delta=0.5)

        # 2.0x speed should cut time in half (~3.0 seconds)
        est_fast = TextChunker.estimate_duration_seconds(words_15, speed_multiplier=2.0)
        self.assertAlmostEqual(est_fast, 3.0, delta=0.5)

    def test_sentence_splitting_with_abbreviations(self):
        text = "Dr. Smith went to Washington D.C. yesterday. He met Mr. Jones for lunch! Did they enjoy it?"
        sentences = TextChunker.split_into_sentences(text)
        # Should NOT split on Dr. or Mr.
        self.assertTrue(any("Dr. Smith" in s for s in sentences))
        self.assertTrue(any("Mr. Jones" in s for s in sentences))
        self.assertTrue(len(sentences) >= 2)

    def test_chunking_respects_max_chars(self):
        long_paragraph = (
            "Voice cloning technology requires careful processing. First, the audio is analyzed for pitch and formants. "
            "Then, linguistic representations are matched against spectral envelopes. Finally, a neural vocoder stitches "
            "the audio frames together seamlessly into natural speech."
        )
        chunks = TextChunker.chunk_text(long_paragraph, max_chars_per_chunk=120)
        self.assertTrue(len(chunks) >= 2)
        for chunk in chunks:
            self.assertLessEqual(len(chunk), 160)

    def test_empty_string_handling(self):
        self.assertEqual(TextChunker.split_into_sentences(""), [])
        self.assertEqual(TextChunker.chunk_text(""), [])
        self.assertEqual(TextChunker.estimate_duration_seconds(""), 0.0)


if __name__ == "__main__":
    unittest.main()

