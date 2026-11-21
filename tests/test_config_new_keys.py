"""Sanitize tests for input_device and first_run_done."""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from tests.whisper_test_support import install_cyberscribe_import_stubs  # noqa: E402


class ConfigNewKeysTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        install_cyberscribe_import_stubs()
        import CyberScribe  # noqa: E402

        cls._cyber = CyberScribe

    def test_defaults(self):
        cfg = self._cyber.sanitize_config({})
        self.assertEqual(cfg["input_device"], "")
        self.assertFalse(cfg["first_run_done"])

    def test_input_device_string(self):
        cfg = self._cyber.sanitize_config({"input_device": "  USB Mic  "})
        self.assertEqual(cfg["input_device"], "USB Mic")

    def test_first_run_done_coercion(self):
        cfg = self._cyber.sanitize_config({"first_run_done": "yes"})
        self.assertTrue(cfg["first_run_done"])
        cfg2 = self._cyber.sanitize_config({"first_run_done": 0})
        self.assertFalse(cfg2["first_run_done"])


if __name__ == "__main__":
    unittest.main()