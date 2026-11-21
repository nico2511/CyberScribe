"""Configuration defaults and sanitization (no CyberScribe runtime import)."""

from __future__ import annotations

from audio_devices import sanitize_input_device_name
from audio_pre_buffer import clamp_pre_buffer_ms

VALID_LANGUAGES = {
    "auto", "en", "fr", "de", "es", "it", "ja", "zh", "nl", "uk", "pt", "ru",
}
VALID_MODELS = {"tiny", "base", "small", "medium", "large-v3"}
VALID_DEVICES = {"auto", "cpu", "cuda"}
VALID_COMPUTE = {"int8", "int8_float16", "float16", "float32"}
VALID_PROFILES = {"fast", "balanced", "accurate"}
MAX_RECORD_SECONDS_CAP = 600

DEFAULT_CONFIG = {
    "hotkey": "F8",
    "language": "fr",
    "model_size": "base",
    "device": "auto",
    "compute_type": "int8",
    "transcription_profile": "fast",
    "max_record_seconds": 25,
    "pre_buffer_ms": 1000,
    "check_updates": True,
    "models_dir": "",
    "log_pipeline_timings": False,
    "beeps": False,
    "input_device": "",
    "first_run_done": False,
}

ALLOWED_KEYS = set(DEFAULT_CONFIG.keys())


def sanitize_config(data, *, normalize_hotkey):
    """Keep only known keys and coerce values to safe defaults."""
    if not isinstance(data, dict):
        return DEFAULT_CONFIG.copy()

    cfg = DEFAULT_CONFIG.copy()
    for key in ALLOWED_KEYS:
        if key not in data:
            continue
        cfg[key] = data[key]

    hotkey = normalize_hotkey(cfg.get("hotkey"))
    cfg["hotkey"] = hotkey[:32] if hotkey else DEFAULT_CONFIG["hotkey"]

    language = str(cfg.get("language") or "fr").lower()
    cfg["language"] = language if language in VALID_LANGUAGES else "fr"

    model_size = str(cfg.get("model_size") or "base").lower()
    cfg["model_size"] = model_size if model_size in VALID_MODELS else "base"

    device = str(cfg.get("device") or "auto").lower()
    cfg["device"] = device if device in VALID_DEVICES else "auto"

    compute_type = str(cfg.get("compute_type") or "int8").lower()
    cfg["compute_type"] = compute_type if compute_type in VALID_COMPUTE else "int8"

    profile = str(cfg.get("transcription_profile") or "fast").lower()
    cfg["transcription_profile"] = profile if profile in VALID_PROFILES else "fast"

    try:
        max_seconds = int(cfg.get("max_record_seconds"))
    except (TypeError, ValueError):
        max_seconds = DEFAULT_CONFIG["max_record_seconds"]
    cfg["max_record_seconds"] = max(0, min(max_seconds, MAX_RECORD_SECONDS_CAP))

    cfg["pre_buffer_ms"] = clamp_pre_buffer_ms(cfg.get("pre_buffer_ms"))

    check_updates = cfg.get("check_updates")
    if isinstance(check_updates, bool):
        cfg["check_updates"] = check_updates
    elif isinstance(check_updates, str):
        cfg["check_updates"] = check_updates.strip().lower() in ("1", "true", "yes", "on")
    else:
        cfg["check_updates"] = bool(DEFAULT_CONFIG["check_updates"])

    log_timings = cfg.get("log_pipeline_timings")
    if isinstance(log_timings, bool):
        cfg["log_pipeline_timings"] = log_timings
    elif isinstance(log_timings, str):
        cfg["log_pipeline_timings"] = log_timings.strip().lower() in (
            "1",
            "true",
            "yes",
            "on",
        )
    else:
        cfg["log_pipeline_timings"] = bool(DEFAULT_CONFIG["log_pipeline_timings"])

    beeps = cfg.get("beeps")
    if isinstance(beeps, bool):
        cfg["beeps"] = beeps
    elif isinstance(beeps, str):
        cfg["beeps"] = beeps.strip().lower() in ("1", "true", "yes", "on")
    else:
        cfg["beeps"] = bool(DEFAULT_CONFIG["beeps"])

    first_run = cfg.get("first_run_done")
    if isinstance(first_run, bool):
        cfg["first_run_done"] = first_run
    elif isinstance(first_run, str):
        cfg["first_run_done"] = first_run.strip().lower() in ("1", "true", "yes", "on")
    else:
        cfg["first_run_done"] = bool(DEFAULT_CONFIG["first_run_done"])

    models_dir = cfg.get("models_dir")
    if models_dir is None:
        cfg["models_dir"] = ""
    else:
        cfg["models_dir"] = str(models_dir).strip()[:512]

    cfg["input_device"] = sanitize_input_device_name(cfg.get("input_device"))
    return cfg