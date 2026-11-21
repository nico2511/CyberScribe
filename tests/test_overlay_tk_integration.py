"""Integration tests that build the real Tk overlay (needs DISPLAY / Xvfb)."""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from overlay_ui import (  # noqa: E402
    OverlayState,
    StatusOverlay,
    format_pasted_detail,
    format_record_timer,
    recording_display_tick,
)

def _display_usable() -> bool:
    if not os.environ.get("DISPLAY"):
        return False
    try:
        import tkinter as tk

        root = tk.Tk()
        root.withdraw()
        root.destroy()
        return True
    except Exception:
        return False


@unittest.skipUnless(_display_usable(), "DISPLAY manquant (lancer avec xvfb-run -a)")
class OverlayTkIntegrationTest(unittest.TestCase):
    def setUp(self):
        import tkinter as tk

        self._tk = tk
        self.root = tk.Tk()
        self.root.withdraw()
        self.overlay = StatusOverlay(self.root)
        self._elapsed = 7.0

    def tearDown(self):
        try:
            self.overlay.hide()
        except Exception:
            pass
        try:
            self.root.destroy()
        except Exception:
            pass

    def _pump(self, n=2):
        for _ in range(n):
            self.root.update_idletasks()
            self.root.update()

    def test_all_six_states_construct_without_tcl_error(self):
        cases = [
            (OverlayState.LISTENING, "● Écoute", "", format_record_timer(7, 25), 1000),
            (OverlayState.ENDING_SOON, "● Fin dans 3 s", "", format_record_timer(22, 25), 1000),
            (OverlayState.TRANSCRIBING, "Transcription…", "■ ■ ■ base · CPU", "", 0),
            (OverlayState.PASTED, "✓ Collé", format_pasted_detail(142, 1.2), "", 0),
            (OverlayState.ERROR, "✕ Micro introuvable", "Rebranche-le, puis F8", "", 0),
            (OverlayState.CANCELLED, "Annulé", "Rien n'a été collé", "", 0),
        ]
        for state, pill, detail, timer, pre_ms in cases:
            with self.subTest(state=state.value):
                self.overlay.hide()
                self.overlay.show_state(
                    state,
                    pill_text=pill,
                    detail_text=detail,
                    timer_text=timer,
                    pre_buffer_ms=pre_ms,
                )
                self._pump()
                self.assertIsNotNone(self.overlay.window)

    def test_chrono_updates_on_vu_tick_without_state_change(self):
        self.overlay.set_timer_provider(lambda: (self._elapsed, 25))
        self.overlay.set_level_provider(lambda: 0.3)
        self.overlay.show_state(
            OverlayState.LISTENING,
            pill_text="● Écoute",
            timer_text=format_record_timer(self._elapsed, 25),
            pre_buffer_ms=1000,
        )
        self._pump()
        before = self.overlay._timer.cget("text")
        self._elapsed = 9.0
        self.overlay._vu_tick()
        self._pump()
        after = self.overlay._timer.cget("text")
        self.assertEqual(before, "0:07 / 0:25")
        self.assertEqual(after, "0:09 / 0:25")
        tick = recording_display_tick(22.0, 25)
        self.assertEqual(tick.state, OverlayState.ENDING_SOON)

    def test_listening_overlay_from_cold_start(self):
        """Same path as F8 → start_recording_action → _show_listening_overlay."""
        self.overlay.set_level_provider(lambda: 0.1)
        self.overlay.set_timer_provider(lambda: (0.0, 25))
        self.overlay.show_state(
            OverlayState.LISTENING,
            pill_text="● Écoute",
            timer_text=format_record_timer(0, 25),
            pre_buffer_ms=1000,
        )
        self._pump(4)


if __name__ == "__main__":
    unittest.main()