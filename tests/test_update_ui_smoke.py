"""Headless Tk smoke test for the checksum prompts and settings section."""

import os
import queue
import sys
import tempfile
import time
import types
import unittest


def _install_import_stubs():
    def ensure(name):
        mod = sys.modules.get(name)
        if mod is None:
            mod = types.ModuleType(name)
            sys.modules[name] = mod
        return mod

    pyaudio = ensure("pyaudio")
    pyaudio.PyAudio = lambda: None
    pyaudio.paInt16 = 8
    ensure("pystray")
    pyperclip = ensure("pyperclip")
    pyperclip.copy = lambda text: None
    ensure("pyautogui")
    pynput = ensure("pynput")
    keyboard = ensure("pynput.keyboard")
    pynput.keyboard = keyboard
    pil = ensure("PIL")
    image = ensure("PIL.Image")
    pil.Image = image
    faster = ensure("faster_whisper")
    faster.WhisperModel = object


def _tk_available():
    try:
        import tkinter as tk

        root = tk.Tk()
        root.withdraw()
        root.destroy()
        return True
    except Exception:
        return False


_install_import_stubs()

try:
    import tkinter as tk
    import CyberScribe
    from updater import make_sha256_verification
except Exception:  # pragma: no cover - environment without a display or Tk
    tk = None
    CyberScribe = None
    make_sha256_verification = None


def _walk(widget):
    yield widget
    for child in widget.winfo_children():
        yield from _walk(child)


def _widget_text(widget):
    chunks = []
    try:
        text = widget.cget("text")
    except Exception:
        text = ""
    if text:
        chunks.append(str(text))
    try:
        var_name = widget.cget("textvariable")
    except Exception:
        var_name = ""
    if var_name:
        try:
            chunks.append(str(widget.getvar(var_name)))
        except Exception:
            pass
    if widget.winfo_class() == "Entry":
        try:
            chunks.append(widget.get())
        except Exception:
            pass
    return "\n".join(chunks)


def _all_text(widget):
    return "\n".join(_widget_text(child) for child in _walk(widget))


def _buttons(widget):
    return [child for child in _walk(widget) if child.winfo_class() == "Button"]


def _entries(widget):
    return [child for child in _walk(widget) if child.winfo_class() == "Entry"]


@unittest.skipUnless(tk is not None and _tk_available(), "Tk display is not available")
class UpdateUiSmokeTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._old_app_dir = CyberScribe.APP_DIR
        self._old_config = CyberScribe.CONFIG_FILE
        CyberScribe.APP_DIR = self._tmp.name
        CyberScribe.CONFIG_FILE = os.path.join(self._tmp.name, "config.json")
        self.app = CyberScribe.CyberScribeApp.__new__(CyberScribe.CyberScribeApp)
        self.app.root = tk.Tk()
        self.app.root.withdraw()
        self.app.settings_window = None
        self.app._sha_job = 0
        self.app._settings_sha_var = None
        self.app._settings_sha_hint = None
        self.app.queue = queue.Queue()
        self.app.tray_icon = None
        self.app.hotkey_listener = None
        self.app.config = CyberScribe.ConfigManager()

    def tearDown(self):
        try:
            self.app.root.update()
            time.sleep(0.12)
            self.app.root.update()
        except Exception:
            pass
        try:
            if self.app.settings_window is not None:
                self.app.settings_window.destroy()
        except Exception:
            pass
        try:
            self.app.root.destroy()
        except Exception:
            pass
        CyberScribe.APP_DIR = self._old_app_dir
        CyberScribe.CONFIG_FILE = self._old_config
        self._tmp.cleanup()

    def _pump_hash(self, timeout=2.0):
        deadline = time.time() + timeout
        while time.time() < deadline:
            self.app.root.update()
            try:
                msg = self.app.queue.get_nowait()
            except queue.Empty:
                time.sleep(0.02)
                continue
            if isinstance(msg, tuple) and msg and msg[0] == "local_exe_sha256":
                self.app._apply_local_exe_sha256(msg[1], msg[2], msg[3])
                self.app.root.update()
                return
        self.fail("local EXE hash was not delivered")

    def test_settings_hash_is_async_and_copyable(self):
        digest = "ab" * 32
        finished = {"ok": False}

        def slow_hash():
            time.sleep(0.3)
            finished["ok"] = True
            return digest

        original_frozen = CyberScribe.is_frozen_build
        original_hash = CyberScribe.local_frozen_exe_sha256
        CyberScribe.is_frozen_build = lambda: True
        CyberScribe.local_frozen_exe_sha256 = slow_hash
        try:
            self.app.open_settings_window()
            self.app.root.update()
            window = self.app.settings_window
            self.assertIsNotNone(window)
            text = _all_text(window)
            self.assertIn("Aucun texte dicté n'est envoyé.", text)
            self.assertIn("SHA256 de cet exécutable", text)
            self.assertIn("Calcul en cours…", text)
            self.assertFalse(finished["ok"])
            self._pump_hash()
            self.app.root.update()
            entries = [entry.get() for entry in _entries(window)]
            self.assertIn(digest, entries)
            self.assertIn("Calcul local terminé", _all_text(window))
            copied = {}

            def capture(value):
                copied["value"] = value
                return True

            self.app._copy_to_clipboard = capture
            for button in _buttons(window):
                if button.cget("text") == "Copier":
                    button.invoke()
                    break
            else:
                self.fail("copy button missing")
            self.assertEqual(copied["value"], digest)
            self.assertIn("Copié dans le presse-papiers.", _all_text(window))
        finally:
            CyberScribe.is_frozen_build = original_frozen
            CyberScribe.local_frozen_exe_sha256 = original_hash

    def test_script_mode_explains_missing_exe_hash(self):
        self.app.open_settings_window()
        self.app.root.update()
        text = _all_text(self.app.settings_window)
        self.assertIn("Ce mode script n'a pas d'exécutable figé.", text)
        self.assertNotIn("Calcul en cours…", text)

    def _drive_dialog(self, press):
        def interact():
            dialogs = [
                widget
                for widget in self.app.root.winfo_children()
                if isinstance(widget, tk.Toplevel) and widget is not self.app.settings_window
            ]
            self.assertTrue(dialogs)
            dialog = dialogs[-1]
            self._seen.append(_all_text(dialog))
            self._seen_entries.append([entry.get() for entry in _entries(dialog)])
            for button in _buttons(dialog):
                if button.cget("text") == press:
                    button.invoke()
                    return
            self.fail(f"button {press!r} not found")

        self._seen = []
        self._seen_entries = []
        self.app.root.after(50, interact)

    def test_before_download_shows_full_hash_and_confirm(self):
        verification = make_sha256_verification(
            sidecar_present=True, expected="cd" * 32, actual=None
        )
        body, hashes, mode = self.app._before_download_copy("9.9.9", verification)
        self.assertEqual(mode, "confirm")
        self.assertIn("Télécharger et installer maintenant ?", body)
        self._drive_dialog("Télécharger")
        confirmed = self.app._checksum_dialog(
            "CyberScribe — mise à jour",
            body,
            hashes,
            tone="info",
            confirm_text="Télécharger",
            cancel_text="Annuler",
        )
        self.assertTrue(confirmed)
        self.assertIn("cd" * 32, self._seen_entries[0])
        self.assertIn("aperçu cdcdcdcdcdcdcdcd…cdcdcdcd", self._seen[0])

    def test_missing_sidecar_warns_but_can_continue(self):
        verification = make_sha256_verification(
            sidecar_present=False, expected=None, actual=None
        )
        body, hashes, mode = self.app._before_download_copy("1.2.0", verification)
        self.assertEqual(mode, "warn")
        self.assertIn("ne publie pas CyberScribe.exe.sha256", body)
        self._drive_dialog("Continuer quand même")
        confirmed = self.app._checksum_dialog(
            "CyberScribe — mise à jour",
            body,
            hashes,
            tone="warn",
            confirm_text="Continuer quand même",
            cancel_text="Annuler",
        )
        self.assertTrue(confirmed)
        self.assertIn("Vous pouvez continuer.", self._seen[0])

    def test_verified_after_download_mentions_result(self):
        digest = "ef" * 32
        verification = make_sha256_verification(
            sidecar_present=True, expected=digest, actual=digest
        )
        body, hashes, mode, confirm = self.app._after_download_copy("9.9.9", verification)
        self.assertEqual(mode, "confirm")
        self.assertEqual(confirm, "Installer et redémarrer")
        self.assertIn("Somme SHA256 vérifiée", body)
        self._drive_dialog("Annuler")
        confirmed = self.app._checksum_dialog(
            "CyberScribe — mise à jour",
            body,
            hashes,
            tone="info",
            confirm_text=confirm,
            cancel_text="Annuler",
        )
        self.assertFalse(confirmed)
        self.assertIn(digest, self._seen_entries[0])

    def test_mismatch_dialog_shows_both_hashes(self):
        verification = make_sha256_verification(
            sidecar_present=True, expected="ab" * 32, actual="cd" * 32
        )
        self._drive_dialog("Fermer")
        self.app._show_sha_mismatch(verification)
        blob = self._seen[0]
        self.assertIn("Téléchargement refusé.", blob)
        self.assertIn("ab" * 32, blob)
        self.assertIn("cd" * 32, blob)
        self.assertNotIn("Installer", blob)
