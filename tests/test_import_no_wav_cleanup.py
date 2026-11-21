"""Importing modules must not delete active cyberscribe_*.wav captures in TEMP."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import types
import unittest
import wave

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, REPO_ROOT)


def _write_min_wav(path: str) -> None:
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(b"\x00\x00" * 100)


class ImportPreservesCaptureWavTest(unittest.TestCase):
    def test_dictation_pipeline_transcribe_preserves_wav(self):
        fd, path = tempfile.mkstemp(suffix=".wav", prefix="cyberscribe_")
        os.close(fd)
        try:
            _write_min_wav(path)
            import dictation_pipeline

            class _Model:
                def transcribe(self, _audio, **_kwargs):
                    return iter(()), types.SimpleNamespace()

            dictation_pipeline.transcribe_with_model(
                _Model(),
                path,
                profile="fast",
                language="fr",
            )
            self.assertTrue(os.path.isfile(path), "transcribe_with_model removed capture wav")
        finally:
            if os.path.isfile(path):
                os.remove(path)

    def test_fresh_cyberscribe_import_preserves_temp_wav(self):
        """Subprocess: first import of CyberScribe must not run orphan WAV cleanup."""
        script = r"""
import os, sys, tempfile, wave
repo = {repo!r}
sys.path.insert(0, repo)
from tests.whisper_test_support import install_cyberscribe_import_stubs
install_cyberscribe_import_stubs()
fd, path = tempfile.mkstemp(suffix=".wav", prefix="cyberscribe_")
os.close(fd)
with wave.open(path, "wb") as wf:
    wf.setnchannels(1)
    wf.setsampwidth(2)
    wf.setframerate(16000)
    wf.writeframes(b"\\x00\\x00" * 4)
import CyberScribe
if not os.path.isfile(path):
    raise SystemExit("CyberScribe import deleted active capture wav")
""".format(repo=REPO_ROOT)
        subprocess.check_call([sys.executable, "-c", script], cwd=REPO_ROOT)

    def test_bootstrap_runtime_only_cleans_orphans(self):
        """bootstrap_runtime may remove orphans; a plain import must not."""
        fd, path = tempfile.mkstemp(suffix=".wav", prefix="cyberscribe_")
        os.close(fd)
        try:
            _write_min_wav(path)
            import importlib

            import audio_wav  # noqa: F401

            importlib.reload(audio_wav)
            self.assertTrue(os.path.isfile(path), "audio_wav import removed capture wav")
        finally:
            if os.path.isfile(path):
                os.remove(path)


if __name__ == "__main__":
    unittest.main()