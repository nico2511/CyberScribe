"""Work-area overlay placement (no Tk)."""

from __future__ import annotations

import unittest

from overlay_placement import WorkArea, compute_overlay_xy
from overlay_ui import OVERLAY_H, OVERLAY_W, OVERLAY_BOTTOM_MARGIN_PX, recording_display_tick, OverlayState


class ComputeOverlayXYTest(unittest.TestCase):
    def test_taskbar_bottom_default_margin(self):
        work = WorkArea(0, 0, 1920, 1040)
        x, y = compute_overlay_xy(
            work, overlay_w=OVERLAY_W, overlay_h=OVERLAY_H, margin=OVERLAY_BOTTOM_MARGIN_PX
        )
        self.assertEqual(x, (1920 - OVERLAY_W) // 2)
        self.assertEqual(y, 1040 - OVERLAY_H - OVERLAY_BOTTOM_MARGIN_PX)

    def test_taskbar_top(self):
        work = WorkArea(0, 48, 1920, 1080)
        x, y = compute_overlay_xy(work, overlay_w=OVERLAY_W, overlay_h=OVERLAY_H, margin=24)
        self.assertEqual(x, (1920 - OVERLAY_W) // 2)
        self.assertEqual(y, 1080 - OVERLAY_H - 24)

    def test_taskbar_left(self):
        work = WorkArea(72, 0, 1920, 1080)
        x, y = compute_overlay_xy(work, overlay_w=OVERLAY_W, overlay_h=OVERLAY_H, margin=28)
        self.assertEqual(x, 72 + (1848 - OVERLAY_W) // 2)
        self.assertEqual(y, 1080 - OVERLAY_H - 28)

    def test_small_work_area_clamps_top(self):
        work = WorkArea(0, 0, 400, 20)
        x, y = compute_overlay_xy(work, overlay_w=OVERLAY_W, overlay_h=OVERLAY_H, margin=28)
        self.assertGreaterEqual(y, 0)


class RecordingChronoTickTest(unittest.TestCase):
    def test_timer_advances_each_tick(self):
        t1 = recording_display_tick(7.0, 25).timer_text
        t2 = recording_display_tick(8.0, 25).timer_text
        self.assertNotEqual(t1, t2)
        self.assertEqual(t1, "0:07 / 0:25")
        self.assertEqual(t2, "0:08 / 0:25")

    def test_ending_soon_progress(self):
        tick = recording_display_tick(22.5, 25)
        self.assertEqual(tick.state, OverlayState.ENDING_SOON)
        self.assertIn("Fin dans", tick.pill_text)
        self.assertAlmostEqual(tick.progress_frac, 0.9, places=1)


if __name__ == "__main__":
    unittest.main()