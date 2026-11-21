"""Reproducible dictation tests on reference WAV fixtures.

Model-dependent cases skip when no local ``tiny`` faster-whisper cache exists
(see tests/whisper_test_support.py). CI runs the skip path by design.
"""

from __future__ import annotations

import hashlib
import os
import re
import sys
import tempfile
import unittest
import wave

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

    def _concat_wavs(self, paths: list[str]) -> str:
        fd, out = tempfile.mkstemp(suffix=".wav")
        os.close(fd)
        frames = b""
        params = None
        for path in paths:
            with wave.open(path, "rb") as wf:
                if params is None:
                    params = (
                        wf.getnchannels(),
                        wf.getsampwidth(),
                        wf.getframerate(),
                    )
                else:
                    self.assertEqual(
                        (wf.getnchannels(), wf.getsampwidth(), wf.getframerate()),
                        params,
                    )
                frames += wf.readframes(wf.getnframes())
        with wave.open(out, "wb") as wf:
            wf.setnchannels(params[0])
            wf.setsampwidth(params[1])
            wf.setframerate(params[2])
            wf.writeframes(frames)
        return out

    def test_pre_buffer_silence_then_speech_no_clipping(self):
        """Simulate 1 s pre-roll silence + immediate speech (VAD should ignore silence)."""
        silence = reference_wav("silence_only.wav")
        speech = reference_wav("speech_immediate_start.wav")
        path = self._concat_wavs([silence, speech])
        try:
            result = transcribe_with_model(
                self._model, path, profile="fast", language="en"
            )
            self.assertGreater(result.segment_count, 0)
            self.assertIsNotNone(result.first_segment_start_s)
            assert result.first_segment_start_s is not None
            self.assertGreater(result.first_segment_start_s, 0.4)
            self.assertLess(result.first_segment_start_s, 1.5)
        finally:
            os.remove(path)

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
