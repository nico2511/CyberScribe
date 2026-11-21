"""WAV edge cases (odd PCM length, auto-stop capture) — no PyAV fallback."""

from __future__ import annotations

import os
import struct
import sys
import tempfile
import types
import unittest
import wave

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# Reuse wav loader stubs from test_wav_load
from tests import test_wav_load as _wav_stub  # noqa: E402

_wav_stub._install_import_stubs()
import CyberScribe  # noqa: E402
import dictation_pipeline  # noqa: E402


def _write_wav_raw(path: str, pcm: bytes, *, rate: int = 16000) -> None:
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(rate)
        wf.writeframes(pcm)


class OddPcmWavTest(unittest.TestCase):
    def test_load_truncates_odd_trailing_byte(self):
        pcm = b"\x00\x01" * 50 + b"\x02"
        fd, path = tempfile.mkstemp(suffix=".wav", prefix="cyberscribe_")
        os.close(fd)
        try:
            _write_wav_raw(path, pcm)
            audio = CyberScribe.load_wav_mono_f32(path)
            self.assertEqual(len(audio), 50)
        finally:
            os.remove(path)

    def test_normalize_pcm16_mono_bytes(self):
        self.assertEqual(CyberScribe.normalize_pcm16_mono_bytes(b"abc"), b"ab")
        self.assertEqual(CyberScribe.normalize_pcm16_mono_bytes(b"abcd"), b"abcd")

    def test_auto_stop_sized_capture_roundtrip(self):
        """~25 s at 16 kHz with a trailing odd byte still transcribable in numpy."""
        samples = 16000 * 25
        pcm = (b"\x00\x64" * samples) + b"\xff"
        fd, path = tempfile.mkstemp(suffix=".wav", prefix="cyberscribe_")
        os.close(fd)
        try:
            _write_wav_raw(path, pcm)
            audio = CyberScribe.load_wav_mono_f32(path)
            self.assertGreater(len(audio), samples - 2)
        finally:
            os.remove(path)


class TranscribeNoPyAvFallbackTest(unittest.TestCase):
    def test_transcribe_raises_when_wav_unloadable(self):
        class _Model:
            def transcribe(self, _audio, **_kwargs):
                raise AssertionError("PyAV path must not be used")

        fd, path = tempfile.mkstemp(suffix=".wav", prefix="cyberscribe_")
        os.close(fd)
        try:
            _write_wav_raw(path, b"\x00\x00", rate=44100)
            with self.assertRaises(ValueError):
                dictation_pipeline.transcribe_with_model(
                    _Model(),
                    path,
                    profile="fast",
                    language="fr",
                )
        finally:
            os.remove(path)

    def test_transcribe_uses_numpy_array_not_path(self):
        calls = {}

        class _Model:
            def transcribe(self, audio_input, **_kwargs):
                calls["kind"] = type(audio_input).__name__
                return iter(()), types.SimpleNamespace()

        fd, path = tempfile.mkstemp(suffix=".wav", prefix="cyberscribe_")
        os.close(fd)
        try:
            _write_wav_raw(path, struct.pack("<8h", *([1000] * 8)))
            dictation_pipeline.transcribe_with_model(_Model(), path, profile="fast", language="fr")
            self.assertIn(calls["kind"], ("ndarray", "_I16"))
        finally:
            os.remove(path)


if __name__ == "__main__":
    unittest.main()