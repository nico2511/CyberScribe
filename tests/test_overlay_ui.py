"""Unit tests for overlay state helpers and vu-meter (no Tk GUI)."""

from __future__ import annotations

import math
import os
import struct
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from tests.whisper_test_support import install_cyberscribe_import_stubs  # noqa: E402

from overlay_ui import (  # noqa: E402
    OverlayState,
    ending_soon_remaining,
    format_pasted_detail,
    format_record_timer,
    overlay_state_for_recording,
    pcm16_chunk_rms,
    pre_buffer_bar_count,
    vu_meter_bar_levels,
)


class FormatRecordTimerTest(unittest.TestCase):
    def test_with_max(self):
        self.assertEqual(format_record_timer(7, 25), "0:07 / 0:25")
        self.assertEqual(format_record_timer(0, 25), "0:00 / 0:25")

    def test_without_max(self):
        self.assertEqual(format_record_timer(65, 0), "1:05")


class FormatPastedDetailTest(unittest.TestCase):
    def test_short_duration_comma(self):
        self.assertEqual(format_pasted_detail(142, 1.2), "142 caractères · 1,2 s")

    def test_long_duration_rounded(self):
        self.assertEqual(format_pasted_detail(10, 12.4), "10 caractères · 12 s")


class EndingSoonTest(unittest.TestCase):
    def test_inside_window(self):
        self.assertEqual(ending_soon_remaining(22.0, 25), 3)
        self.assertEqual(ending_soon_remaining(24.2, 25), 1)

    def test_outside_window(self):
        self.assertIsNone(ending_soon_remaining(10.0, 25))
        self.assertIsNone(ending_soon_remaining(25.0, 25))


class OverlayStateMachineTest(unittest.TestCase):
    def test_listening_vs_ending(self):
        self.assertEqual(overlay_state_for_recording(5, 25), OverlayState.LISTENING)
        self.assertEqual(overlay_state_for_recording(23, 25), OverlayState.ENDING_SOON)


class SanitizeBeepsTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        install_cyberscribe_import_stubs()
        import CyberScribe  # noqa: E402

        cls._cyber = CyberScribe

    def test_beeps_default(self):
        cfg = self._cyber.sanitize_config({})
        self.assertFalse(cfg["beeps"])

    def test_beeps_coercion(self):
        cfg = self._cyber.sanitize_config({"beeps": "yes"})
        self.assertTrue(cfg["beeps"])
        cfg2 = self._cyber.sanitize_config({"beeps": 0})
        self.assertFalse(cfg2["beeps"])


class VuMeterTest(unittest.TestCase):
    def test_rms_silence(self):
        chunk = struct.pack("<8h", *([0] * 8))
        self.assertEqual(pcm16_chunk_rms(chunk), 0.0)

    def test_rms_full_scale(self):
        chunk = struct.pack("<h", 32767)
        level = pcm16_chunk_rms(chunk)
        self.assertTrue(0.9 < level <= 1.0)

    def test_pre_buffer_split(self):
        history = [0.1 * (i % 5) for i in range(20)]
        bars, split = vu_meter_bar_levels(history, pre_buffer_bars=5)
        self.assertEqual(len(bars), 48)
        self.assertEqual(split, 5)

    def test_no_pre_buffer(self):
        history = [0.5, 0.6]
        bars, split = vu_meter_bar_levels(history, pre_buffer_bars=0)
        self.assertEqual(split, -1)

    def test_pre_buffer_bar_count_zero(self):
        self.assertEqual(pre_buffer_bar_count(0), 0)

    def test_pre_buffer_bar_count_one_second(self):
        self.assertEqual(pre_buffer_bar_count(1000, refresh_hz=25.0), 25)


if __name__ == "__main__":
    unittest.main()