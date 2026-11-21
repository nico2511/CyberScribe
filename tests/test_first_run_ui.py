"""First-run wizard visibility and Plus tard semantics."""

from __future__ import annotations

import os
import sys
import types
import unittest
from unittest import mock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from tests.whisper_test_support import install_cyberscribe_import_stubs  # noqa: E402

install_cyberscribe_import_stubs()


class FakeConfig:
    def __init__(self):
        self.values = {"first_run_done": False}

    def get(self, key):
        return self.values.get(key)

    def set(self, key, value):
        self.values[key] = value


class FirstRunLogicTest(unittest.TestCase):
    def test_maybe_show_only_when_not_done(self):
        from first_run_ui import maybe_show_first_run

        app = types.SimpleNamespace(
            config=FakeConfig(),
            first_run_window=None,
        )

        with mock.patch("first_run_ui.open_first_run_wizard") as opener:
            maybe_show_first_run(app)
            opener.assert_called_once_with(app)

        with mock.patch("first_run_ui.open_first_run_wizard") as opener:
            app.config.values["first_run_done"] = True
            maybe_show_first_run(app)
            opener.assert_not_called()

    def test_plus_tard_marks_done(self):
        from first_run_ui import open_first_run_wizard

        import tkinter as tk

        if not hasattr(tk.Tk(), "withdraw"):
            self.skipTest("Tk not available in this environment")
        root = tk.Tk()
        root.withdraw()
        app = types.SimpleNamespace(
            root=root,
            config=FakeConfig(),
            first_run_window=None,
            recorder=types.SimpleNamespace(audio=types.SimpleNamespace(get_device_count=lambda: 0)),
            has_nvidia=False,
            apply_input_device=lambda name: None,
            transcriber=types.SimpleNamespace(loading=False, reload=lambda: None),
            update_tray_icon=lambda **k: None,
            config_set_seen=[],
        )
        app.config.set = lambda k, v: app.config.values.__setitem__(k, v)

        open_first_run_wizard(app)
        for child in app.first_run_window.winfo_children():
            for footer in child.winfo_children():
                if footer.winfo_class() == "Frame":
                    for btn in footer.winfo_children():
                        if getattr(btn, "cget", None) and btn.cget("text") == "[ PLUS TARD ]":
                            btn.invoke()
                            break
        self.assertTrue(app.config.values.get("first_run_done"))
        root.destroy()


if __name__ == "__main__":
    unittest.main()