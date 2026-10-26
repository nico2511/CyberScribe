"""Helpers for optional faster-whisper integration tests (no transcript logging)."""

from __future__ import annotations

import os
import sys
import types
import unittest
from typing import Optional, Tuple


def install_cyberscribe_import_stubs() -> None:
    """Minimal stubs so CyberScribe imports without GUI/audio hardware."""

    def ensure(name: str):
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
        tkinter.filedialog = ensure("tkinter.filedialog")
        tkinter.ttk = ensure("tkinter.ttk")
        tkinter.messagebox = ensure("tkinter.messagebox")

    pyaudio = ensure("pyaudio")

    class _StubPyAudio:
        paInt16 = 8

        def get_sample_size(self, _fmt):
            return 2

        def terminate(self):
            return None

        def open(self, **kwargs):
            return None

    pyaudio.PyAudio = _StubPyAudio
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
    mouse.Button = types.SimpleNamespace(
        left="l", right="r", middle="m", x1="x1", x2="x2"
    )
    ensure("PIL")
    ensure("PIL.Image")
    ensure("faster_whisper").WhisperModel = object


def test_models_dir() -> str:
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    custom = os.environ.get("CYBERSCRIBE_TEST_MODELS_DIR", "").strip()
    if custom:
        return os.path.expanduser(os.path.expandvars(custom))
    return os.path.join(root, "tests", ".models_cache")


def whisper_model_cache_ready(models_dir: str, model_size: str = "tiny") -> bool:
    """True if a local faster-whisper snapshot appears present (no download)."""
    if not models_dir or not os.path.isdir(models_dir):
        return False
    needle = f"faster-whisper-{model_size}".lower()
    for dirpath, dirnames, filenames in os.walk(models_dir):
        low = dirpath.lower()
        if needle not in low:
            continue
        if filenames:
            if any(
                name.endswith(".bin") or name == "model.bin" or name.endswith(".json")
                for name in filenames
            ):
                return True
        # Hugging Face cache stores payloads under blobs/ without extensions.
        if os.path.basename(dirpath).lower() == "blobs" and filenames:
            return True
        if "snapshots" in dirnames:
            return True
    return False


def load_whisper_model_cpu(model_size: str = "tiny"):
    """Load WhisperModel on CPU or raise SkipTest if offline cache missing."""
    models_dir = test_models_dir()
    os.makedirs(models_dir, exist_ok=True)
    if not whisper_model_cache_ready(models_dir, model_size):
        raise unittest.SkipTest(
            "Whisper model not cached locally (set CYBERSCRIBE_TEST_MODELS_DIR or "
            "pre-download tiny weights into tests/.models_cache). CI skips by design."
        )
    prev = os.environ.get("HF_HUB_OFFLINE")
    os.environ["HF_HUB_OFFLINE"] = "1"
    try:
        fw = sys.modules.get("faster_whisper")
        if fw is not None and not getattr(fw, "__file__", None):
            del sys.modules["faster_whisper"]
        from faster_whisper import WhisperModel

        return WhisperModel(
            model_size,
            device="cpu",
            compute_type="int8",
            download_root=models_dir,
        )
    except Exception as exc:
        raise unittest.SkipTest(f"Whisper model unavailable offline: {exc}") from exc
    finally:
        if prev is None:
            os.environ.pop("HF_HUB_OFFLINE", None)
        else:
            os.environ["HF_HUB_OFFLINE"] = prev


def reference_wav(name: str) -> str:
    return os.path.join(os.path.dirname(__file__), "fixtures", "reference", name)
