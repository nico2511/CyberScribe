"""PCM WAV helpers and transcription profile presets (no app side effects)."""

from __future__ import annotations

import wave

PROFILE_PRESETS = {
    "fast": {
        "beam_size": 1,
        "best_of": 1,
        "vad_filter": True,
        "vad_parameters": {"min_silence_duration_ms": 250},
        "condition_on_previous_text": False,
        "no_speech_threshold": 0.7,
        "log_prob_threshold": -2.0,
    },
    "balanced": {
        "beam_size": 3,
        "best_of": 2,
        "vad_filter": True,
        "vad_parameters": {"min_silence_duration_ms": 400},
        "condition_on_previous_text": False,
        "no_speech_threshold": 0.75,
        "log_prob_threshold": -1.5,
    },
    "accurate": {
        "beam_size": 5,
        "best_of": 3,
        "vad_filter": True,
        "vad_parameters": {"min_silence_duration_ms": 500},
        "condition_on_previous_text": False,
        "no_speech_threshold": 0.8,
        "log_prob_threshold": -1.0,
    },
}


def normalize_pcm16_mono_bytes(raw: bytes) -> bytes:
    """Drop a trailing byte so PCM16 mono frame data is an even length."""
    if not raw:
        return b""
    if len(raw) % 2:
        return raw[:-1]
    return raw


def load_wav_mono_f32(path, expected_rate=16000):
    """Load a PCM WAV as float32 mono for faster-whisper (avoids PyAV decode)."""
    import numpy as np

    with wave.open(path, "rb") as wf:
        channels = wf.getnchannels()
        rate = wf.getframerate()
        sampwidth = wf.getsampwidth()
        frames = normalize_pcm16_mono_bytes(wf.readframes(wf.getnframes()))

    if sampwidth != 2:
        raise ValueError(f"Unsupported sample width: {sampwidth} (need 16-bit PCM)")
    if rate != expected_rate:
        raise ValueError(f"Unexpected sample rate: {rate} (need {expected_rate})")

    audio = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
    if channels > 1:
        audio = audio.reshape(-1, channels).mean(axis=1)
    return audio