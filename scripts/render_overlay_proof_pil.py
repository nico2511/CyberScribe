#!/usr/bin/env python3
"""Static overlay state renders for PR proof when Tk/Xvfb is unavailable."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from PIL import Image, ImageDraw, ImageFont

from overlay_ui import STATE_PALETTE, OverlayState, format_pasted_detail, format_record_timer

OUT = os.environ.get("CYBERSCRIBE_SCREENSHOTS", "/opt/cursor/artifacts/overlay-states")
W, H = 400, 38


def _font(name: str, size: int):
    for path in (
        f"/usr/share/fonts/truetype/dejavu/DejaVuSans-{name}.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    ):
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def draw_state(state: OverlayState, pill: str, detail: str, timer: str = "") -> Image.Image:
    pal = STATE_PALETTE[state]
    img = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, 0, W - 1, H - 1], outline=pal.border, width=2)
    draw.rectangle([1, 1, 142, H - 2], fill=pal.pill_bg)
    draw.rectangle([143, 1, W - 2, H - 2], fill="#0b1120")
    font = _font("Bold", 13)
    mono = _font("", 12)
    draw.text((12, 10), pill, fill=pal.pill_fg, font=font)
    if detail:
        draw.text((152, 18), detail, fill=pal.detail_fg, font=_font("", 11))
    if timer:
        tw = draw.textlength(timer, font=mono)
        draw.text((W - 12 - tw, 18), timer, fill=pal.detail_fg, font=mono)
    if state in (OverlayState.LISTENING, OverlayState.ENDING_SOON):
        bar_color = "#00f2ff" if state == OverlayState.LISTENING else "#f59e0b"
        for i in range(30):
            bh = 4 + (i % 5) * 3
            x = 155 + i * 7
            draw.rectangle([x, 8 + (14 - bh), x + 4, 22], fill=bar_color)
        draw.line([210, 6, 210, 24], fill="#ffffff", width=1)
    return img


def main():
    os.makedirs(OUT, exist_ok=True)
    specs = [
        ("01-ecoute", OverlayState.LISTENING, "● Écoute", "", format_record_timer(7, 25)),
        ("02-fin-proche", OverlayState.ENDING_SOON, "● Fin dans 3 s", "", format_record_timer(22, 25)),
        ("03-transcription", OverlayState.TRANSCRIBING, "Transcription…", "■ ■ ■ base · CPU", ""),
        ("04-colle", OverlayState.PASTED, "✓ Collé", format_pasted_detail(142, 1.2), ""),
        ("05-erreur", OverlayState.ERROR, "✕ Micro introuvable", "Rebranche-le, puis F8", ""),
        ("06-annule", OverlayState.CANCELLED, "Annulé", "Rien n'a été collé", ""),
    ]
    for name, state, pill, detail, timer in specs:
        path = os.path.join(OUT, f"{name}.png")
        draw_state(state, pill, detail, timer).save(path)
        print(path)


if __name__ == "__main__":
    main()