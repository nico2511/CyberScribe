#!/usr/bin/env python3
"""Capture configuration tabs, first-run steps, and overlay transition frames under Xvfb."""

from __future__ import annotations

import os
import sys
import tempfile
import types

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
OUT = os.environ.get("CYBERSCRIBE_SCREENSHOTS", "/opt/cursor/artifacts/pr2-ui")
os.makedirs(OUT, exist_ok=True)

import subprocess
import tkinter as tk
import types

# Stub heavy deps only — keep real Tk for captures.
for name in ("pystray", "pyautogui", "faster_whisper", "pyperclip", "pynput"):
    if name not in sys.modules:
        sys.modules[name] = types.ModuleType(name)
sys.modules.setdefault("pyaudio", types.ModuleType("pyaudio"))
pyaudio = sys.modules["pyaudio"]
pyaudio.paInt16 = 8


class _FakePyAudio:
    paInt16 = 8

    def get_device_count(self):
        return 2

    def get_device_info_by_index(self, index):
        return {"name": "Micro virtuel (Xvfb)", "maxInputChannels": 1 if index else 0}

    def get_sample_size(self, _fmt):
        return 2

    def terminate(self):
        return None

    def open(self, **kwargs):
        return types.SimpleNamespace(
            read=lambda *a, **k: b"\x00" * 1024,
            stop_stream=lambda: None,
            close=lambda: None,
        )


pyaudio.PyAudio = _FakePyAudio

pynput = sys.modules["pynput"]
pynput.keyboard = types.ModuleType("pynput.keyboard")
pynput.mouse = types.ModuleType("pynput.mouse")
pynput.keyboard.GlobalHotKeys = lambda *a, **k: types.SimpleNamespace(
    start=lambda: None, stop=lambda: None, join=lambda *a, **k: None
)
pynput.keyboard.Listener = lambda *a, **k: types.SimpleNamespace(
    start=lambda: None, stop=lambda: None, join=lambda *a, **k: None
)
pynput.mouse.Listener = lambda *a, **k: types.SimpleNamespace(
    start=lambda: None, stop=lambda: None, join=lambda *a, **k: None
)
pynput.mouse.Button = types.SimpleNamespace(x1="x1", x2="x2", middle="middle")
sys.modules["faster_whisper"].WhisperModel = object

import CyberScribe
from first_run_ui import open_first_run_wizard
from settings_ui import open_settings_window
from overlay_ui import OverlayState, StatusOverlay


def _save(widget, name):
    widget.update_idletasks()
    widget.update()
    path = os.path.join(OUT, name)
    wid = widget.winfo_id()
    try:
        subprocess.run(
            ["import", "-silent", "-window", str(wid), path],
            check=True,
            timeout=10,
        )
        print(f"saved {path}")
    except Exception as exc:
        print(f"skip {name}: {exc}", file=sys.stderr)


def main():
    cfg_path = os.path.join(tempfile.mkdtemp(), "config.json")
    with open(cfg_path, "w", encoding="utf-8") as f:
        f.write('{"first_run_done": true}')
    CyberScribe.CONFIG_FILE = cfg_path

    root = tk.Tk()
    root.withdraw()
    app = CyberScribe.CyberScribeApp()
    app.config.set("first_run_done", True)
    app._tray_mode = "ready"
    app.transcriber.loading = False
    app._has_nvidia = False

    open_settings_window(app)
    app.root.update()

    def _click_tab(tab_name: str):
        def _walk(widget):
            for child in widget.winfo_children():
                if child.winfo_class() == "Label" and child.cget("text") == tab_name:
                    child.event_generate("<Button-1>")
                    return True
                if _walk(child):
                    return True
            return False

        _walk(app.settings_window)
        app.root.update_idletasks()
        app.root.update()

    tabs = ["Dictée", "Micro", "Moteur", "Système"]
    for tab in tabs:
        _click_tab(tab)
        safe = tab.lower().replace("è", "e").replace("é", "e")
        _save(app.settings_window, f"config-tab-{safe}.png")

    app.settings_window.destroy()
    app.config.set("first_run_done", False)
    open_first_run_wizard(app)
    app.root.update()
    def _click_continue(win):
        def _walk(widget):
            for child in widget.winfo_children():
                if child.winfo_class() == "Button" and child.cget("text") == ">> CONTINUER <<":
                    child.invoke()
                    return True
                if _walk(child):
                    return True
            return False

        _walk(win)

    for step in (1, 2, 3):
        _save(app.first_run_window, f"first-run-step-{step}.png")
        if step < 3:
            _click_continue(app.first_run_window)
        app.root.update()

    overlay = StatusOverlay(root)
    overlay.show_state(
        OverlayState.LISTENING,
        pill_text="● Écoute",
        timer_text="0:01 / 0:25",
        pre_buffer_ms=1000,
    )
    root.update()
    _save(overlay.window, "overlay-listening.png")
    overlay.show_state(
        OverlayState.TRANSCRIBING,
        pill_text="◌ Transcription",
        detail_text="Analyse locale…",
    )
    for delay in (40, 80, 120):
        root.update()
        root.after(delay)
        root.update_idletasks()
        _save(overlay.window, f"overlay-transition-{delay}ms.png")

    app.recorder.terminate()
    root.destroy()
    print(f"Captures in {OUT}")


if __name__ == "__main__":
    main()