"""Unit tests for hotkey normalization, display, and pynput formatting."""

import os
import sys
import types
import unittest


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

    class _Button:
        left = "left"
        right = "right"
        middle = "middle"
        x1 = "x1"
        x2 = "x2"

    mouse.Button = _Button
    mouse.Listener = lambda *a, **k: types.SimpleNamespace(
        start=lambda: None, stop=lambda: None, join=lambda *a, **k: None
    )
    keyboard.GlobalHotKeys = lambda *a, **k: types.SimpleNamespace(
        start=lambda: None, stop=lambda: None, join=lambda *a, **k: None
    )
    keyboard.Listener = lambda *a, **k: types.SimpleNamespace(
        start=lambda: None, stop=lambda: None, join=lambda *a, **k: None
    )
    pil = ensure("PIL")
    image = ensure("PIL.Image")
    pil.Image = image
    faster = ensure("faster_whisper")
    faster.WhisperModel = object


_install_import_stubs()
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import CyberScribe  # noqa: E402


class HotkeyHelpersTest(unittest.TestCase):
    def test_normalize_keyboard(self):
        self.assertEqual(CyberScribe.normalize_hotkey("f8"), "F8")
        self.assertEqual(CyberScribe.normalize_hotkey("ctrl+shift+f8"), "ctrl+shift+F8")
        self.assertEqual(CyberScribe.normalize_hotkey("Control + F8"), "ctrl+F8")

    def test_normalize_mouse_aliases(self):
        self.assertEqual(CyberScribe.normalize_hotkey("x1"), "mouse_x1")
        self.assertEqual(CyberScribe.normalize_hotkey("button5"), "mouse_x2")
        self.assertEqual(CyberScribe.normalize_hotkey("mouse_middle"), "mouse_middle")

    def test_is_mouse_hotkey(self):
        self.assertTrue(CyberScribe.is_mouse_hotkey("mouse_x1"))
        self.assertFalse(CyberScribe.is_mouse_hotkey("F8"))

    def test_display_hotkey(self):
        self.assertIn("X1", CyberScribe.display_hotkey("x1"))
        self.assertEqual(CyberScribe.display_hotkey("F8"), "F8")

    def test_format_hotkey_keyboard(self):
        self.assertEqual(CyberScribe.format_hotkey("F8"), "<f8>")
        self.assertEqual(CyberScribe.format_hotkey("ctrl+shift+f8"), "<ctrl>+<shift>+<f8>")

    def test_format_hotkey_mouse_passthrough(self):
        self.assertEqual(CyberScribe.format_hotkey("mouse_x1"), "mouse_x1")

    def test_sanitize_accepts_mouse(self):
        cfg = CyberScribe.sanitize_config({"hotkey": "x2"})
        self.assertEqual(cfg["hotkey"], "mouse_x2")


if __name__ == "__main__":
    unittest.main()
