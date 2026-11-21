"""Guard against duplicate process_audio on the same WAV (regression PR #12)."""

from __future__ import annotations

import os
import sys
import tempfile
import threading
import types
import unittest
import wave

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from tests.whisper_test_support import install_cyberscribe_import_stubs  # noqa: E402
import dictation_pipeline  # noqa: E402


def _minimal_wav(path: str, *, frames: int = 8000) -> None:
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(b"\x00\x00" * frames)


class ProcessAudioGuardTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        install_cyberscribe_import_stubs()
        import CyberScribe  # noqa: E402

        cls._cyber = CyberScribe

    def setUp(self):
        self.app = object.__new__(self._cyber.CyberScribeApp)
        self.app._audio_process_lock = threading.Lock()
        self.app._audio_process_paths = set()
        self.app.recorder = types.SimpleNamespace(_safe_remove=lambda p: os.path.exists(p) and os.remove(p))
        self.app.config = types.SimpleNamespace(
            get=lambda k, default=None: default if k != "transcription_profile" else "fast"
        )
        self.app.queue = types.SimpleNamespace(put=lambda *a, **k: None)
        self.app.transcriber = types.SimpleNamespace(
            model=object(),
            loading=False,
            _transcribe_lock=threading.Lock(),
        )
        calls = {"n": 0}

        def _transcribe_with_model(*args, **kwargs):
            calls["n"] += 1
            return types.SimpleNamespace(text="ok", audio_duration_s=1.0)

        self._orig_transcribe = dictation_pipeline.transcribe_with_model
        dictation_pipeline.transcribe_with_model = _transcribe_with_model
        self.calls = calls
        self.app.paste_text = lambda _t: 0.0
        self.app._cyber = self._cyber

        fd, self.wav_path = tempfile.mkstemp(suffix=".wav", prefix="cyberscribe_")
        os.close(fd)
        _minimal_wav(self.wav_path)

    def tearDown(self):
        try:
            dictation_pipeline.transcribe_with_model = self._orig_transcribe
        except AttributeError:
            pass
        try:
            os.remove(self.wav_path)
        except OSError:
            pass

    def test_duplicate_process_audio_skips_second_call(self):
        barrier = threading.Barrier(2)

        def worker():
            barrier.wait()
            self._cyber.CyberScribeApp.process_audio(self.app, self.wav_path)

        t1 = threading.Thread(target=worker)
        t2 = threading.Thread(target=worker)
        t1.start()
        t2.start()
        t1.join(timeout=5)
        t2.join(timeout=5)
        self.assertEqual(self.calls["n"], 1)
        self.assertFalse(os.path.exists(self.wav_path))

    def test_missing_file_does_not_crash(self):
        path = self.wav_path
        os.remove(path)
        self._cyber.CyberScribeApp.process_audio(self.app, path)
        self.assertEqual(self.calls["n"], 0)


if __name__ == "__main__":
    unittest.main()