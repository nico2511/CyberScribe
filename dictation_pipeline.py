"""Shared dictation pipeline helpers (transcription + timing metadata).

Privacy: never log or persist transcribed text from here — only durations and counts.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

import wave

# Lazy import of CyberScribe pieces avoids circular imports at module load.
_PROFILE_PRESETS = None
_load_wav_mono_f32 = None


def _cyber():
    global _PROFILE_PRESETS, _load_wav_mono_f32
    if _PROFILE_PRESETS is None:
        import CyberScribe as cs

        _PROFILE_PRESETS = cs.PROFILE_PRESETS
        _load_wav_mono_f32 = cs.load_wav_mono_f32
    return _PROFILE_PRESETS, _load_wav_mono_f32


@dataclass
class PipelineTimings:
    """Seconds measured with time.perf_counter()."""

    audio_finalize_s: float = 0.0
    transcribe_s: float = 0.0
    paste_s: float = 0.0

    @property
    def total_s(self) -> float:
        return self.audio_finalize_s + self.transcribe_s + self.paste_s


@dataclass
class TranscribeResult:
    text: str
    timings: PipelineTimings = field(default_factory=PipelineTimings)
    segment_count: int = 0
    first_segment_start_s: Optional[float] = None
    last_segment_end_s: Optional[float] = None
    audio_duration_s: float = 0.0


def wav_duration_seconds(path: str) -> float:
    with wave.open(path, "rb") as wf:
        frames = wf.getnframes()
        rate = wf.getframerate()
    if rate <= 0:
        return 0.0
    return frames / float(rate)


def transcribe_kwargs_for_profile(profile: str, language: Optional[str]) -> Dict[str, Any]:
    presets, _ = _cyber()
    preset = presets.get(profile, presets["fast"])
    lang = None if (language or "").lower() == "auto" else language
    return {
        "beam_size": preset["beam_size"],
        "best_of": preset["best_of"],
        "language": lang,
        "condition_on_previous_text": preset["condition_on_previous_text"],
        "vad_filter": preset["vad_filter"],
        "vad_parameters": preset["vad_parameters"],
        "no_speech_threshold": preset["no_speech_threshold"],
        "log_prob_threshold": preset["log_prob_threshold"],
    }


def transcribe_with_model(
    model,
    audio_path: str,
    *,
    profile: str = "fast",
    language: str = "fr",
) -> TranscribeResult:
    """Run faster-whisper on a 16 kHz mono PCM16 WAV path."""
    _, load_wav = _cyber()
    timings = PipelineTimings()
    t0 = time.perf_counter()
    try:
        audio_input = load_wav(audio_path)
    except Exception:
        audio_input = audio_path
    timings.audio_finalize_s = time.perf_counter() - t0

    kwargs = transcribe_kwargs_for_profile(profile, language)
    t1 = time.perf_counter()
    segments, _info = model.transcribe(audio_input, **kwargs)
    segment_list = list(segments)
    text = "".join(seg.text for seg in segment_list).strip()
    timings.transcribe_s = time.perf_counter() - t1

    first_start = segment_list[0].start if segment_list else None
    last_end = segment_list[-1].end if segment_list else None
    return TranscribeResult(
        text=text,
        timings=timings,
        segment_count=len(segment_list),
        first_segment_start_s=first_start,
        last_segment_end_s=last_end,
        audio_duration_s=wav_duration_seconds(audio_path),
    )


def simulate_paste(
    paste_fn: Optional[Callable[[str], None]] = None,
    *,
    paste_sleep_s: float = 0.3,
) -> float:
    """Return seconds spent in paste step (clipboard + Ctrl+V or mock)."""
    t0 = time.perf_counter()

    def _noop(_text: str) -> None:
        if paste_sleep_s > 0:
            time.sleep(paste_sleep_s)

    fn = paste_fn or _noop
    fn("")
    return time.perf_counter() - t0


def summarize_durations(values: List[float]) -> Dict[str, float]:
    if not values:
        return {"min": 0.0, "median": 0.0, "max": 0.0}
    ordered = sorted(values)
    n = len(ordered)
    mid = ordered[n // 2] if n % 2 else (ordered[n // 2 - 1] + ordered[n // 2]) / 2.0
    return {"min": ordered[0], "median": mid, "max": ordered[-1]}


def format_timing_log(
    profile: str,
    device: str,
    model_size: str,
    audio_duration_s: float,
    timings: PipelineTimings,
    *,
    text_len: int,
) -> str:
    return (
        f"Pipeline timing profile={profile} device={device} model={model_size} "
        f"audio_s={audio_duration_s:.3f} finalize_s={timings.audio_finalize_s:.3f} "
        f"transcribe_s={timings.transcribe_s:.3f} paste_s={timings.paste_s:.3f} "
        f"total_s={timings.total_s:.3f} text_len={text_len}"
    )
