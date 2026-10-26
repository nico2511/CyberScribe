#!/usr/bin/env python3
"""Generate deterministic 16 kHz mono PCM16 reference WAVs for dictation tests.

Run from repo root:
  python tests/fixtures/generate_reference_wavs.py

Speech clips are trimmed from the Silero VAD test WAV (MIT, upstream
``silero-vad/tests/data/test.wav``) when ``reference/_silero_source.wav`` is absent
and network is available. Silence is synthetic PCM. Re-run after changing sources.
"""

from __future__ import annotations

import math
import os
import shutil
import struct
import subprocess
import sys
import urllib.request
import wave

SAMPLE_RATE = 16000
OUT_DIR = os.path.join(os.path.dirname(__file__), "reference")


def _write_pcm16(path: str, samples: list[int]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    raw = struct.pack("<" + "h" * len(samples), *samples)
    _write_pcm16_bytes(path, raw)


def _write_pcm16_bytes(path: str, raw: bytes) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with wave.open(path, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(raw)


def _silence_seconds(seconds: float) -> list[int]:
    n = int(SAMPLE_RATE * seconds)
    return [0] * n


def _tone_burst(start_s: float, duration_s: float, freq_hz: float, amplitude: float = 0.35) -> dict[int, float]:
    """Return sparse index -> sample contributions to mix."""
    out: dict[int, float] = {}
    start_i = int(start_s * SAMPLE_RATE)
    n = int(duration_s * SAMPLE_RATE)
    for i in range(n):
        t = i / SAMPLE_RATE
        env = min(1.0, i / (SAMPLE_RATE * 0.02), (n - i) / (SAMPLE_RATE * 0.02))
        val = amplitude * env * math.sin(2 * math.pi * freq_hz * t)
        idx = start_i + i
        out[idx] = out.get(idx, 0.0) + val
    return out


def _mix_to_int16(sparse: dict[int, float], total_samples: int) -> list[int]:
    samples = [0.0] * total_samples
    for idx, val in sparse.items():
        if 0 <= idx < total_samples:
            samples[idx] += val
    pcm = []
    for val in samples:
        clamped = max(-1.0, min(1.0, val))
        pcm.append(int(clamped * 32767))
    return pcm


def write_silence_only() -> None:
    path = os.path.join(OUT_DIR, "silence_only.wav")
    _write_pcm16(path, _silence_seconds(3.0))


def _espeak_wav(text: str, path: str) -> bool:
    exe = shutil.which("espeak-ng") or shutil.which("espeak")
    if not exe:
        return False
    tmp = path + ".part.wav"
    try:
        subprocess.run(
            [exe, "-v", "fr", "-s", "130", "-w", tmp, text],
            check=True,
            capture_output=True,
        )
        # espeak writes 22050 Hz typically — resample with Python if needed
        with wave.open(tmp, "rb") as wf:
            channels = wf.getnchannels()
            rate = wf.getframerate()
            width = wf.getsampwidth()
            frames = wf.readframes(wf.getnframes())
        if width != 2:
            return False
        import array

        data = array.array("h")
        data.frombytes(frames)
        if channels > 1:
            mono = []
            for i in range(0, len(data), channels):
                mono.append(data[i])
            data = array.array("h", mono)
        if rate != SAMPLE_RATE:
            # linear resample
            ratio = SAMPLE_RATE / float(rate)
            new_len = int(len(data) * ratio)
            resampled = []
            for i in range(new_len):
                src = i / ratio
                i0 = int(src)
                i1 = min(i0 + 1, len(data) - 1)
                frac = src - i0
                resampled.append(int(data[i0] * (1 - frac) + data[i1] * frac))
            data = array.array("h", resampled)
        _write_pcm16(path, list(data))
        return True
    except Exception:
        return False
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)


SILERO_SOURCE_URL = (
    "https://github.com/snakers4/silero-vad/raw/master/tests/data/test.wav"
)


def _ensure_silero_source() -> str:
    cached = os.path.join(OUT_DIR, "_silero_source.wav")
    if os.path.isfile(cached):
        return cached
    urllib.request.urlretrieve(SILERO_SOURCE_URL, cached)
    return cached


def _read_mono_pcm16(path: str) -> bytes:
    with wave.open(path, "rb") as wf:
        if (
            wf.getnchannels() != 1
            or wf.getsampwidth() != 2
            or wf.getframerate() != SAMPLE_RATE
        ):
            raise ValueError(f"Unexpected WAV format: {path}")
        return wf.readframes(wf.getnframes())


def _slice_seconds(raw: bytes, start_s: float, end_s: float) -> bytes:
    bps = SAMPLE_RATE * 2
    return raw[int(start_s * bps) : int(end_s * bps)]


def write_speech_immediate() -> None:
    path = os.path.join(OUT_DIR, "speech_immediate_start.wav")
    try:
        src = _ensure_silero_source()
        raw = _read_mono_pcm16(src)
        _write_pcm16_bytes(path, _slice_seconds(raw, 0, 2.5))
        return
    except Exception:
        pass
    phrase = "Bonjour, ceci est un test de dictée immédiate."
    if _espeak_wav(phrase, path):
        return
    total = int(SAMPLE_RATE * 2.5)
    sparse: dict[int, float] = {}
    for freq in (180, 240, 320):
        sparse.update(_tone_burst(0.0, 2.2, freq, amplitude=0.25))
    _write_pcm16(path, _mix_to_int16(sparse, total))


def write_speech_with_pause() -> None:
    path = os.path.join(OUT_DIR, "speech_long_pause.wav")
    try:
        src = _ensure_silero_source()
        raw = _read_mono_pcm16(src)
        part_a = _slice_seconds(raw, 0.0, 1.4)
        part_b = _slice_seconds(raw, 8.0, 9.5)
        gap = b"\x00\x00" * int(SAMPLE_RATE * 1.8)
        _write_pcm16_bytes(path, part_a + gap + part_b)
        return
    except Exception:
        pass
    phrase_a = "Première partie du message."
    phrase_b = "Deuxième partie après la pause."
    if shutil.which("espeak-ng") or shutil.which("espeak"):
        part_a = path + ".a.wav"
        part_b = path + ".b.wav"
        gap = os.path.join(OUT_DIR, "_gap.wav")
        try:
            if _espeak_wav(phrase_a, part_a) and _espeak_wav(phrase_b, part_b):
                _write_pcm16(gap, _silence_seconds(1.8))
                chunks = []
                for p in (part_a, gap, part_b):
                    with wave.open(p, "rb") as wf:
                        chunks.append(wf.readframes(wf.getnframes()))
                with wave.open(part_a, "rb") as wf:
                    params = wf.getparams()
                with wave.open(path, "wb") as out:
                    out.setparams(params)
                    for c in chunks:
                        out.writeframes(c)
                return
        finally:
            for p in (part_a, part_b, gap):
                if os.path.exists(p):
                    os.remove(p)

    total = int(SAMPLE_RATE * 5.5)
    sparse: dict[int, float] = {}
    sparse.update(_tone_burst(0.05, 1.4, 200, amplitude=0.3))
    sparse.update(_tone_burst(3.35, 1.5, 210, amplitude=0.3))
    _write_pcm16(path, _mix_to_int16(sparse, total))


def main() -> int:
    write_silence_only()
    write_speech_immediate()
    write_speech_with_pause()
    print(f"Wrote reference WAVs under {OUT_DIR}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
