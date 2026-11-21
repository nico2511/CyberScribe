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
    TRANSITION_MS,
    ending_soon_remaining,
    format_pasted_detail,
    format_record_timer,
    interpolate_palette,
    lerp_hex_color,
    overlay_state_for_recording,
    pcm16_chunk_rms,
    pre_buffer_bar_count,
    recording_display_tick,
    scale_vu_level,
    vu_bar_height,
    vu_meter_bar_levels,
    STATE_PALETTE,
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

    def test_recording_tick_updates_timer_not_only_on_state_change(self):
        tick_a = recording_display_tick(3.0, 25)
        tick_b = recording_display_tick(4.0, 25)
        self.assertEqual(tick_a.state, tick_b.state)
        self.assertNotEqual(tick_a.timer_text, tick_b.timer_text)


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


class OverlayTransitionTest(unittest.TestCase):
    def test_lerp_midpoint(self):
        mid = lerp_hex_color("#000000", "#ffffff", 0.5)
        self.assertIn(mid.lower(), ("#7f7f7f", "#808080"))

    def test_transition_duration_constants(self):
        self.assertEqual(TRANSITION_MS, 200)

    def test_interpolate_palette_endpoints(self):
        src = STATE_PALETTE[OverlayState.LISTENING]
        dst = STATE_PALETTE[OverlayState.TRANSCRIBING]
        self.assertEqual(interpolate_palette(src, dst, 0.0).border, src.border)
        self.assertEqual(interpolate_palette(src, dst, 1.0).border, dst.border)


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

    def test_scale_vu_level_typical_speech(self):
        self.assertGreater(scale_vu_level(0.05), 0.2)
        self.assertGreater(vu_bar_height(scale_vu_level(0.05), 22), 4)


if __name__ == "__main__":
    unittest.main()