#!/usr/bin/env python3
"""Measure dictation latency on reference WAVs (durations only — no transcript output).

Example:
  python bench_dictation_latency.py --iterations 3 --profiles fast,balanced,accurate

Requires a local faster-whisper ``tiny`` cache under tests/.models_cache unless
CYBERSCRIBE_TEST_MODELS_DIR is set. Exits with code 2 when the model is missing.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from typing import Dict, List

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

from dictation_pipeline import (  # noqa: E402
    format_timing_log,
    simulate_paste,
    summarize_durations,
    transcribe_with_model,
    wav_duration_seconds,
)
from tests.whisper_test_support import (  # noqa: E402
    install_cyberscribe_import_stubs,
    load_whisper_model_cpu,
    reference_wav,
    test_models_dir,
    whisper_model_cache_ready,
)


def _parse_profiles(raw: str) -> List[str]:
    items = [p.strip().lower() for p in raw.split(",") if p.strip()]
    allowed = {"fast", "balanced", "accurate"}
    bad = [p for p in items if p not in allowed]
    if bad:
        raise SystemExit(f"Unknown profile(s): {', '.join(bad)}")
    return items or ["fast"]


def run_bench(
    *,
    fixture: str,
    profiles: List[str],
    iterations: int,
    language: str,
    include_paste: bool,
    paste_sleep_s: float,
) -> Dict:
    install_cyberscribe_import_stubs()
    if not os.path.isfile(fixture):
        raise SystemExit(f"Fixture not found: {fixture}")

    models_dir = test_models_dir()
    if not whisper_model_cache_ready(models_dir, "tiny"):
        raise SystemExit(
            "Whisper tiny model not found locally. Pre-download into "
            f"{models_dir} or set CYBERSCRIBE_TEST_MODELS_DIR. No cloud download in bench."
        )

    model = load_whisper_model_cpu("tiny")
    audio_duration_s = wav_duration_seconds(fixture)

    report: Dict = {
        "fixture": os.path.basename(fixture),
        "audio_duration_s": round(audio_duration_s, 3),
        "device": "cpu",
        "model_size": "tiny",
        "iterations": iterations,
        "profiles": {},
    }

    for profile in profiles:
        buckets: Dict[str, List[float]] = {
            "audio_finalize_s": [],
            "transcribe_s": [],
            "paste_s": [],
            "total_s": [],
        }
        for _ in range(iterations):
            t_finalize0 = time.perf_counter()
            # Simulate post-hotkey WAV finalize (read stat / open handle)
            with open(fixture, "rb") as handle:
                handle.read(44)
            audio_finalize_s = time.perf_counter() - t_finalize0

            result = transcribe_with_model(
                model,
                fixture,
                profile=profile,
                language=language,
            )
            text_len = len(result.text)
            paste_s = 0.0
            if include_paste:
                paste_s = simulate_paste(paste_sleep_s=paste_sleep_s)

            timings = result.timings
            timings.audio_finalize_s = audio_finalize_s
            timings.paste_s = paste_s

            buckets["audio_finalize_s"].append(timings.audio_finalize_s)
            buckets["transcribe_s"].append(timings.transcribe_s)
            buckets["paste_s"].append(timings.paste_s)
            buckets["total_s"].append(timings.total_s)

            # One metadata line per iteration (no transcript text)
            print(
                format_timing_log(
                    profile,
                    "cpu",
                    "tiny",
                    audio_duration_s,
                    timings,
                    text_len=text_len,
                )
            )

        report["profiles"][profile] = {
            key: {k: round(v, 4) for k, v in summarize_durations(vals).items()}
            for key, vals in buckets.items()
        }

    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="CyberScribe dictation latency bench")
    parser.add_argument(
        "--fixture",
        default=reference_wav("speech_immediate_start.wav"),
        help="Path to 16 kHz mono PCM16 WAV",
    )
    parser.add_argument("--profiles", default="fast,balanced,accurate")
    parser.add_argument("--iterations", type=int, default=3)
    parser.add_argument("--language", default="fr")
    parser.add_argument(
        "--no-paste",
        action="store_true",
        help="Skip simulated paste delay (Ctrl+V sleep)",
    )
    parser.add_argument(
        "--paste-sleep",
        type=float,
        default=0.3,
        help="Seconds for simulated paste step (matches app default)",
    )
    parser.add_argument("--json", dest="json_out", action="store_true", help="Print JSON summary")
    args = parser.parse_args()

    profiles = _parse_profiles(args.profiles)
    report = run_bench(
        fixture=args.fixture,
        profiles=profiles,
        iterations=max(1, args.iterations),
        language=args.language,
        include_paste=not args.no_paste,
        paste_sleep_s=max(0.0, args.paste_sleep),
    )
    if args.json_out:
        print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
