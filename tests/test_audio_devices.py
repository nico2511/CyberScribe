"""Tests for PyAudio input device resolution (mocked PyAudio)."""

from __future__ import annotations

import os
import sys
import types
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from audio_devices import (  # noqa: E402
    INPUT_DEVICE_NAME_MAX_LEN,
    resolve_input_device_index,
    sanitize_input_device_name,
)


class FakePyAudio:
    def __init__(self, devices):
        self._devices = devices

    def get_device_count(self):
        return len(self._devices)

    def get_device_info_by_index(self, index):
        return self._devices[index]


class ResolveInputDeviceTest(unittest.TestCase):
    def setUp(self):
        self.pya = FakePyAudio(
            [
                {"name": "Speakers", "maxInputChannels": 0},
                {"name": "USB Mic Pro", "maxInputChannels": 2},
                {"name": "Headset", "maxInputChannels": 1},
            ]
        )

    def test_default_empty_name(self):
        res = resolve_input_device_index(self.pya, "")
        self.assertIsNone(res.index)
        self.assertTrue(res.matched_by_name)

    def test_name_found(self):
        res = resolve_input_device_index(self.pya, "USB Mic Pro")
        self.assertEqual(res.index, 1)
        self.assertTrue(res.matched_by_name)

    def test_name_missing_falls_back_to_default(self):
        res = resolve_input_device_index(self.pya, "Missing Mic")
        self.assertIsNone(res.index)
        self.assertFalse(res.matched_by_name)
        self.assertEqual(res.requested_name, "Missing Mic")

    def test_sanitize_truncates(self):
        long_name = "x" * (INPUT_DEVICE_NAME_MAX_LEN + 20)
        self.assertEqual(len(sanitize_input_device_name(long_name)), INPUT_DEVICE_NAME_MAX_LEN)


if __name__ == "__main__":
    unittest.main()