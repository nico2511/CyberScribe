#!/usr/bin/env python3
"""Render overlay states under Xvfb for PR proof (Linux Tk)."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import tkinter as tk  # noqa: E402

from overlay_ui import OverlayState, format_pasted_detail, format_record_timer  # noqa: E402


def main():
    out_dir = os.environ.get("CYBERSCRIBE_SCREENSHOTS", "/opt/cursor/artifacts/overlay-states")
    os.makedirs(out_dir, exist_ok=True)

    root = tk.Tk()
    root.withdraw()
    from overlay_ui import StatusOverlay

    overlay = StatusOverlay(root)

    screens = [
        (
            "01-ecoute",
            OverlayState.LISTENING,
            "● Écoute",
            "",
            format_record_timer(7, 25),
            1000,
        ),
        (
            "02-fin-proche",
            OverlayState.ENDING_SOON,
            "● Fin dans 3 s",
            "",
            format_record_timer(22, 25),
            1000,
        ),
        (
            "03-transcription",
            OverlayState.TRANSCRIBING,
            "Transcription…",
            "■ ■ ■ base · CPU",
            "",
            0,
        ),
        (
            "04-colle",
            OverlayState.PASTED,
            "✓ Collé",
            format_pasted_detail(142, 1.2),
            "",
            0,
        ),
        (
            "05-erreur",
            OverlayState.ERROR,
            "✕ Micro introuvable",
            "Rebranche-le, puis F8",
            "",
            0,
        ),
        (
            "06-annule",
            OverlayState.CANCELLED,
            "Annulé",
            "Rien n'a été collé",
            "",
            0,
        ),
    ]

    for name, state, pill, detail, timer, pre_ms in screens:
        overlay.show_state(
            state,
            pill_text=pill,
            detail_text=detail,
            timer_text=timer,
            pre_buffer_ms=pre_ms,
        )
        root.update_idletasks()
        root.update()
        if state in (OverlayState.LISTENING, OverlayState.ENDING_SOON):
            overlay._vu_history = [0.2 + 0.1 * (i % 4) for i in range(48)]
            overlay._draw_vu_meter()
            root.update()
        path = os.path.join(out_dir, f"{name}.png")
        if overlay.window:
            overlay.window.update_idletasks()
            try:
                from PIL import ImageGrab

                x = overlay.window.winfo_rootx()
                y = overlay.window.winfo_rooty()
                w = overlay.window.winfo_width()
                h = overlay.window.winfo_height()
                img = ImageGrab.grab(bbox=(x, y, x + w, y + h))
                img.save(path)
                print(path)
            except Exception as exc:
                print(f"skip {name}: {exc}", file=sys.stderr)
        overlay.hide()

    root.destroy()


if __name__ == "__main__":
    main()