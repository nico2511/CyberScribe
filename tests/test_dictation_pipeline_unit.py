"""Unit tests for dictation_pipeline helpers (no Whisper)."""

from __future__ import annotations

import os
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from dictation_pipeline import summarize_durations, transcribe_kwargs_for_profile  # noqa: E402
from tests.whisper_test_support import install_cyberscribe_import_stubs  # noqa: E402

install_cyberscribe_import_stubs()


class PipelineHelpersTest(unittest.TestCase):
    def test_summarize_durations(self):
        stats = summarize_durations([0.2, 0.4, 1.0])
        self.assertEqual(stats["min"], 0.2)
        self.assertEqual(stats["median"], 0.4)
        self.assertEqual(stats["max"], 1.0)

    def test_profile_presets_keys(self):
        for profile in ("fast", "balanced", "accurate"):
            kwargs = transcribe_kwargs_for_profile(profile, "fr")
            self.assertTrue(kwargs["vad_filter"])
            self.assertIn("beam_size", kwargs)


if __name__ == "__main__":
    unittest.main()
