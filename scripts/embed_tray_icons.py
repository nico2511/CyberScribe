#!/usr/bin/env python3
"""Regenerate ICON_*_B64 constants in CyberScribe.py from gen_icons.py."""

from __future__ import annotations

import base64
import contextlib
import io
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from gen_icons import VARIANTS, create_icon  # noqa: E402


def main():
    target = ROOT / "CyberScribe.py"
    text = target.read_text(encoding="utf-8")
    for _key, spec in VARIANTS.items():
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            create_icon(spec["head"], spec["eyes"], spec["filename"])
        line = buf.getvalue().strip().split("\n")[0]
        fname = spec["filename"].upper()
        val = line.split("=", 1)[1].strip().strip('"')
        if len(val) % 4 != 0:
            raise SystemExit(f"invalid padding for ICON_{fname}_B64")
        base64.b64decode(val)
        pattern = rf'ICON_{fname}_B64 = "[^"]*"'
        text, n = re.subn(pattern, f'ICON_{fname}_B64 = "{val}"', text, count=1)
        if n != 1:
            raise SystemExit(f"missing ICON_{fname}_B64 in CyberScribe.py")
    target.write_text(text, encoding="utf-8")
    print("Updated tray icon constants in CyberScribe.py")


if __name__ == "__main__":
    main()