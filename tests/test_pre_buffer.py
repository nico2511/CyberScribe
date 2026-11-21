"""Unit tests for in-memory pre-buffer ring and capture junction (no microphone)."""

from __future__ import annotations

import os
import struct
import sys
import tempfile
import unittest
import wave

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from tests.whisper_test_support import install_cyberscribe_import_stubs  # noqa: E402

from audio_pre_buffer import (
    CircularByteBuffer,
    clamp_pre_buffer_ms,
    concat_prebuffer_and_capture,
    pre_buffer_capacity_bytes,
)


class SanitizeConfigPreBufferTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        install_cyberscribe_import_stubs()
        import CyberScribe  # noqa: E402

        cls._cyber = CyberScribe

    def test_sanitize_pre_buffer_ms(self):
        cfg = self._cyber.sanitize_config({"pre_buffer_ms": "500"})
        self.assertEqual(cfg["pre_buffer_ms"], 500)
        cfg2 = self._cyber.sanitize_config({"pre_buffer_ms": 99999})
        self.assertEqual(cfg2["pre_buffer_ms"], 3000)
        cfg3 = self._cyber.sanitize_config({})
        self.assertEqual(cfg3["pre_buffer_ms"], 1000)


class ClampPreBufferMsTest(unittest.TestCase):
    def test_defaults_and_bounds(self):
        self.assertEqual(clamp_pre_buffer_ms(None), 1000)
        self.assertEqual(clamp_pre_buffer_ms(-5), 0)
        self.assertEqual(clamp_pre_buffer_ms(5000), 3000)
        self.assertEqual(clamp_pre_buffer_ms(750), 750)


class CircularByteBufferTest(unittest.TestCase):
    def test_partial_fill_preserves_order(self):
        ring = CircularByteBuffer(8)
        ring.push(b"ab")
        ring.push(b"cd")
        self.assertEqual(ring.snapshot(), b"abcd")
        self.assertEqual(ring.filled_bytes(), 4)

    def test_overflow_drops_oldest(self):
        ring = CircularByteBuffer(6)
        ring.push(b"123")
        ring.push(b"456")
        ring.push(b"78")
        self.assertEqual(ring.snapshot(), b"345678")

    def test_snapshot_is_copy(self):
        ring = CircularByteBuffer(10)
        ring.push(b"abc")
        snap = ring.snapshot()
        ring.push(b"def")
        self.assertEqual(snap, b"abc")
        self.assertEqual(ring.snapshot(), b"abcdef")

    def test_capacity_from_pre_buffer_ms(self):
        cap = pre_buffer_capacity_bytes(1000)
        self.assertEqual(cap, 16000 * 2)
        ring = CircularByteBuffer(cap)
        chunk = bytes(range(256)) * 128
        ring.push(chunk)
        self.assertEqual(ring.filled_bytes(), cap)


class PreBufferCaptureJunctionTest(unittest.TestCase):
    def test_concat_no_duplicate_at_junction(self):
        pre = b"PRE"
        capture = [b"LIVE1", b"LIVE2"]
        merged = concat_prebuffer_and_capture(pre, capture)
        self.assertEqual(merged, b"PRELIVE1LIVE2")
        self.assertNotIn(b"PREPRE", merged)

    def test_simulated_monitor_then_record_sequence(self):
        """Ring capture then live frames match a single contiguous PCM stream."""
        ring = CircularByteBuffer(12)
        chunks_idle = [b"aa", b"bb", b"cc"]
        for ch in chunks_idle:
            ring.push(ch)
        pre = ring.snapshot()
        live = [b"dd", b"ee"]
        merged = concat_prebuffer_and_capture(pre, live)
        self.assertEqual(merged, b"aabbccddee")
        self.assertEqual(len(merged), len(pre) + sum(len(c) for c in live))

    def test_write_wav_from_merged_pcm16(self):
        samples = [100, 200, -300, 400, -500, 600]
        raw = b"".join(struct.pack("<h", s) for s in samples)
        ring = CircularByteBuffer(len(raw))
        ring.push(raw[:4])
        pre = ring.snapshot()
        capture = [raw[4:8], raw[8:]]
        pcm = concat_prebuffer_and_capture(pre, capture)
        fd, path = tempfile.mkstemp(suffix=".wav")
        import os

        os.close(fd)
        try:
            with wave.open(path, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(16000)
                wf.writeframes(pcm)
            with wave.open(path, "rb") as wf:
                self.assertEqual(wf.getnframes(), len(samples))
                back = struct.unpack(
                    "<" + "h" * len(samples), wf.readframes(wf.getnframes())
                )
            self.assertEqual(back, tuple(samples))
        finally:
            os.remove(path)


if __name__ == "__main__":
    unittest.main()