#!/usr/bin/env python3
"""Side-by-side mockup vs render plates for PR proof."""

from __future__ import annotations

import os
import subprocess
import sys
import types

from PIL import Image

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
OUT = os.environ.get("CYBERSCRIBE_PLATES", "/opt/cursor/artifacts/pr2-ui")
MOCK_DIR = os.environ.get(
    "CYBERSCRIBE_MOCKS",
    "/home/ubuntu/.cursor/projects/agent-repos-CyberScribe/assets",
)
os.makedirs(OUT, exist_ok=True)


def plate(mockup: str, render: str, out_name: str, label_mock="Maquette", label_render="Rendu"):
    mp = os.path.join(MOCK_DIR, mockup)
    rn = os.path.join(OUT, render)
    if not os.path.isfile(mp) or not os.path.isfile(rn):
        print(f"skip {out_name}: missing {mp} or {rn}", file=sys.stderr)
        return
    a = Image.open(mp).convert("RGB")
    b = Image.open(rn).convert("RGB")
    h = max(a.height, b.height)
    if a.height != h:
        a = a.resize((int(a.width * h / a.height), h), Image.Resampling.LANCZOS)
    if b.height != h:
        b = b.resize((int(b.width * h / b.height), h), Image.Resampling.LANCZOS)
    gap = 24
    header = 40
    canvas = Image.new("RGB", (a.width + b.width + gap, h + header), (15, 23, 42))
    from PIL import ImageDraw, ImageFont

    draw = ImageDraw.Draw(canvas)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 16)
    except Exception:
        font = ImageFont.load_default()
    draw.text((8, 10), label_mock, fill=(6, 182, 212), font=font)
    draw.text((a.width + gap + 8, 10), label_render, fill=(148, 163, 184), font=font)
    canvas.paste(a, (0, header))
    canvas.paste(b, (a.width + gap, header))
    path = os.path.join(OUT, out_name)
    canvas.save(path)
    print(path)


def main():
    subprocess.run(
        ["xvfb-run", "-a", "python3", os.path.join(ROOT, "scripts", "render_pr2_screenshots.py")],
        check=False,
        env={**os.environ, "CYBERSCRIBE_SCREENSHOTS": OUT},
    )
    plate("mockup-configuration.png", "config-tab-dictee.png", "plate-config-dictee.png")
    # legacy accent filename from older captures
    if not os.path.isfile(os.path.join(OUT, "config-tab-dictee.png")):
        alt = os.path.join(OUT, "config-tab-dictée.png")
        if os.path.isfile(alt):
            os.replace(alt, os.path.join(OUT, "config-tab-dictee.png"))
    plate("mockup-premier-lancement.png", "first-run-step-2.png", "plate-first-run-step2.png")
    plate("mockup-configuration.png", "config-tab-micro.png", "plate-config-micro.png")
    plate("mockup-configuration.png", "config-tab-moteur.png", "plate-config-moteur.png")
    plate("mockup-configuration.png", "config-tab-systeme.png", "plate-config-systeme.png")


if __name__ == "__main__":
    main()