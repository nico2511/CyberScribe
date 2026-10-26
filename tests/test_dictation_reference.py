"""Reproducible dictation tests on reference WAV fixtures.

Model-dependent cases skip when no local ``tiny`` faster-whisper cache exists
(see tests/whisper_test_support.py). CI runs the skip path by design.
"""

from __future__ import annotations

import hashlib
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from dictation_pipeline import transcribe_with_model  # noqa: E402
from tests.whisper_test_support import (  # noqa: E402
    install_cyberscribe_import_stubs,
    load_whisper_model_cpu,
    reference_wav,
)


def _norm_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def _text_fingerprint(text: str) -> str:
    return hashlib.sha256(_norm_text(text).encode("utf-8")).hexdigest()


install_cyberscribe_import_stubs()


class DictationReferenceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._model = None
        try:
            cls._model = load_whisper_model_cpu("tiny")
        except unittest.SkipTest:
            cls._model = None

    def setUp(self):
        if self._model is None:
            self.skipTest(
                "Local Whisper tiny model not cached — dictation tests skipped "
                "(see README / docs/TESTING.md)."
            )

    def test_silence_only_no_transcript(self):
        path = reference_wav("silence_only.wav")
        result = transcribe_with_model(
            self._model, path, profile="fast", language="fr"
        )
        self.assertEqual(result.text.strip(), "")
        self.assertEqual(result.segment_count, 0)

    def test_immediate_start_not_clipped(self):
        path = reference_wav("speech_immediate_start.wav")
        result = transcribe_with_model(
            self._model, path, profile="fast", language="en"
        )
        self.assertGreater(result.segment_count, 0)
        self.assertIsNotNone(result.first_segment_start_s)
        assert result.first_segment_start_s is not None
        self.assertLess(
            result.first_segment_start_s,
            0.6,
            "First speech segment should start near the beginning (VAD must not eat the start).",
        )
        strict = os.environ.get("CYBERSCRIBE_STRICT_TRANSCRIPT_TESTS", "").strip() == "1"
        if strict:
            expected_hash = os.environ.get("CYBERSCRIBE_IMMEDIATE_TEXT_SHA256", "").strip()
            self.assertTrue(expected_hash, "Set CYBERSCRIBE_IMMEDIATE_TEXT_SHA256 for strict mode.")
            self.assertEqual(_text_fingerprint(result.text), expected_hash)

    def test_long_pause_keeps_both_speech_regions(self):
        path = reference_wav("speech_long_pause.wav")
        result = transcribe_with_model(
            self._model, path, profile="balanced", language="en"
        )
        self.assertGreater(result.segment_count, 0)
        self.assertIsNotNone(result.last_segment_end_s)
        assert result.last_segment_end_s is not None
        # Second burst starts ~3.35 s on synthetic fixture; expect coverage past the pause.
        self.assertGreater(result.last_segment_end_s, 3.0)
        strict = os.environ.get("CYBERSCRIBE_STRICT_TRANSCRIPT_TESTS", "").strip() == "1"
        if strict:
            expected_hash = os.environ.get("CYBERSCRIBE_PAUSE_TEXT_SHA256", "").strip()
            self.assertTrue(expected_hash, "Set CYBERSCRIBE_PAUSE_TEXT_SHA256 for strict mode.")
            self.assertEqual(_text_fingerprint(result.text), expected_hash)


if __name__ == "__main__":
    unittest.main()
