"""Unit tests for WAV → float32 loading used by transcription."""

import os
import struct
import sys
import tempfile
import types
import unittest
import wave


def _install_import_stubs():
    def ensure(name):
        mod = sys.modules.get(name)
        if mod is None:
            mod = types.ModuleType(name)
            sys.modules[name] = mod
        return mod

    if "tkinter" not in sys.modules:
        tkinter = ensure("tkinter")
        tkinter.Tk = object
        tkinter.Toplevel = object
        tkinter.Frame = object
        tkinter.Label = object
        tkinter.Entry = object
        tkinter.Button = object
        tkinter.Checkbutton = object
        tkinter.Canvas = object
        tkinter.StringVar = object
        tkinter.BooleanVar = object
        tkinter.TclError = type("TclError", (Exception,), {})
        filedialog = ensure("tkinter.filedialog")
        ttk = ensure("tkinter.ttk")
        messagebox = ensure("tkinter.messagebox")
        tkinter.filedialog = filedialog
        tkinter.ttk = ttk
        tkinter.messagebox = messagebox

    pyaudio = ensure("pyaudio")
    pyaudio.PyAudio = lambda: None
    pyaudio.paInt16 = 8
    ensure("pystray")
    pyperclip = ensure("pyperclip")
    pyperclip.copy = lambda text: None
    ensure("pyautogui")
    pynput = ensure("pynput")
    keyboard = ensure("pynput.keyboard")
    mouse = ensure("pynput.mouse")
    pynput.keyboard = keyboard
    pynput.mouse = mouse
    mouse.Button = types.SimpleNamespace(left="l", right="r", middle="m", x1="x1", x2="x2")
    pil = ensure("PIL")
    image = ensure("PIL.Image")
    pil.Image = image
    faster = ensure("faster_whisper")
    faster.WhisperModel = object

    try:
        import numpy  # noqa: F401
    except ImportError:
        # Minimal stub sufficient for load_wav_mono_f32 in CI without numpy.
        np = ensure("numpy")

        class _I16:
            def __init__(self, data):
                self._data = data

            def astype(self, _dtype):
                return [x / 32768.0 for x in self._data]

        def frombuffer(buf, dtype=None):
            n = len(buf) // 2
            vals = list(struct.unpack("<" + "h" * n, buf))
            return _I16(vals)

        np.frombuffer = frombuffer
        np.int16 = "int16"
        np.float32 = "float32"


_install_import_stubs()
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import CyberScribe  # noqa: E402


class WavLoadTest(unittest.TestCase):
    def test_load_mono_16k(self):
        samples = [0, 16384, -16384, 32767]
        raw = struct.pack("<" + "h" * len(samples), *samples)
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            path = tmp.name
        try:
            with wave.open(path, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(16000)
                wf.writeframes(raw)
            audio = CyberScribe.load_wav_mono_f32(path)
            self.assertEqual(len(audio), 4)
            self.assertAlmostEqual(float(audio[0]), 0.0, places=5)
            self.assertAlmostEqual(float(audio[1]), 0.5, places=4)
        finally:
            os.remove(path)

    def test_rejects_wrong_rate(self):
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            path = tmp.name
        try:
            with wave.open(path, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(44100)
                wf.writeframes(b"\x00\x00")
            with self.assertRaises(ValueError):
                CyberScribe.load_wav_mono_f32(path)
        finally:
            os.remove(path)

    def test_requirements_pin_av_below_19(self):
        req = os.path.join(
            os.path.dirname(__file__), "..", "requirements.txt"
        )
        with open(req, encoding="utf-8") as handle:
            text = handle.read()
        self.assertIn("av>=11,<19", text)


if __name__ == "__main__":
    unittest.main()
