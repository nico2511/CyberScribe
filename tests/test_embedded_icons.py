"""Ensure systray PNG assets embedded in CyberScribe decode and open."""

from __future__ import annotations

import base64
import importlib
import os
import re
import sys
import unittest
from io import BytesIO


def _ensure_real_pillow_image():
    """Avoid broken PIL stubs left in sys.modules by other tests."""
    mod = sys.modules.get("PIL.Image")
    if mod is None or not callable(getattr(mod, "open", None)):
        for name in list(sys.modules):
            if name == "PIL" or name.startswith("PIL."):
                del sys.modules[name]
        return importlib.import_module("PIL.Image")
    return mod


Image = _ensure_real_pillow_image()

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
CYBER_PATH = os.path.join(ROOT, "CyberScribe.py")

ICON_ROLES = {
    "ready": "GRAY",
    "recording": "RED",
    "transcribing": "CYAN",
    "loading": "LOADING",
}


def _load_icon_constants() -> dict[str, str]:
    with open(CYBER_PATH, encoding="utf-8") as handle:
        text = handle.read()
    out = {}
    for role, suffix in ICON_ROLES.items():
        match = re.search(rf'ICON_{suffix}_B64 = "([^"]*)"', text)
        if not match:
            raise KeyError(f"ICON_{suffix}_B64 missing")
        out[role] = match.group(1)
    return out


def _get_icon_image(b64_str: str) -> Image.Image:
    return Image.open(BytesIO(base64.b64decode(b64_str)))


class EmbeddedTrayIconsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        global Image
        Image = _ensure_real_pillow_image()
        cls.icons = _load_icon_constants()

    def setUp(self):
        global Image
        Image = _ensure_real_pillow_image()

    def test_each_icon_decodes_with_valid_padding(self):
        for role, blob in self.icons.items():
            with self.subTest(role=role):
                self.assertEqual(len(blob) % 4, 0, "base64 length must be a multiple of 4")
                raw = base64.b64decode(blob)
                img = Image.open(BytesIO(raw))
                img.load()
                self.assertGreater(img.width, 0)
                self.assertGreater(img.height, 0)

    def test_get_icon_image_like_startup(self):
        """Same steps as CyberScribe.get_icon_image during CyberScribeApp.__init__."""
        for role, blob in self.icons.items():
            with self.subTest(role=role):
                img = _get_icon_image(blob)
                self.assertGreater(img.size[0], 0)


if __name__ == "__main__":
    unittest.main()