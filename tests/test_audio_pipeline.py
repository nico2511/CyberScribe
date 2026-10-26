"""Audio pipeline tests that never require a Whisper model."""

from __future__ import annotations

import os
import struct
import sys
import tempfile
import types
import unittest
import wave


sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from tests.whisper_test_support import install_cyberscribe_import_stubs  # noqa: E402

install_cyberscribe_import_stubs()
import CyberScribe  # noqa: E402
from dictation_pipeline import wav_duration_seconds  # noqa: E402
from tests.whisper_test_support import reference_wav  # noqa: E402


class AudioRecorderWriteTest(unittest.TestCase):
    def test_write_wav_from_frames_matches_recorder_format(self):
        recorder = CyberScribe.AudioRecorder()
        recorder.audio = type(
            "_AudioBackend",
            (),
            {"get_sample_size": lambda _self, _fmt: 2},
        )()
        frames = [struct.pack("<h", sample) for sample in (0, 1000, -1000, 2000)]
        path = recorder._write_wav(frames)
        self.assertTrue(path and os.path.isfile(path))
        try:
            with wave.open(path, "rb") as wf:
                self.assertEqual(wf.getnchannels(), 1)
                self.assertEqual(wf.getsampwidth(), 2)
                self.assertEqual(wf.getframerate(), 16000)
                self.assertEqual(wf.getnframes(), 4)
        finally:
            recorder.cleanup_temps()

    def test_empty_frames_produces_no_file(self):
        recorder = CyberScribe.AudioRecorder()
        self.assertIsNone(recorder._write_wav([]))


class ReferenceFixtureFormatTest(unittest.TestCase):
    def test_reference_wavs_are_16k_mono_pcm16(self):
        for name in (
            "silence_only.wav",
            "speech_immediate_start.wav",
            "speech_long_pause.wav",
        ):
            path = reference_wav(name)
            self.assertTrue(os.path.isfile(path), msg=name)
            with wave.open(path, "rb") as wf:
                self.assertEqual(wf.getnchannels(), 1, msg=name)
                self.assertEqual(wf.getsampwidth(), 2, msg=name)
                self.assertEqual(wf.getframerate(), 16000, msg=name)
            duration = wav_duration_seconds(path)
            self.assertGreater(duration, 0.5, msg=name)

    def test_silence_fixture_is_near_zero_energy(self):
        path = reference_wav("silence_only.wav")
        with wave.open(path, "rb") as wf:
            raw = wf.readframes(wf.getnframes())
        samples = struct.unpack("<" + "h" * (len(raw) // 2), raw)
        peak = max(abs(s) for s in samples)
        self.assertEqual(peak, 0)


if __name__ == "__main__":
    unittest.main()
