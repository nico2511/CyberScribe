# Testing and latency bench

CyberScribe tests are split into **model-free** checks (always run) and **Whisper integration** checks (skipped when no local model cache is present).

## Run all unit tests

```bash
python -m unittest discover -s tests -p "test_*.py" -v
```

On a fresh clone, dictation reference tests **skip** instead of downloading weights. Updater, hotkey, WAV load, and audio pipeline tests still run.

## Test boundary (what needs a model)

| Always runs | Needs local `tiny` cache |
|-------------|---------------------------|
| `test_updater_checksum.py`, `test_hotkey.py`, `test_wav_load.py` | `test_dictation_reference.py` |
| `test_audio_pipeline.py`, `test_dictation_pipeline_unit.py` | `bench_dictation_latency.py` |

Whisper tests use the **`tiny`** model on **CPU** only. They look under `tests/.models_cache` or `CYBERSCRIBE_TEST_MODELS_DIR` and set `HF_HUB_OFFLINE=1` so missing files never trigger a HugHub download in CI.

### Prepare a local model cache (optional)

```bash
export CYBERSCRIBE_TEST_MODELS_DIR="$PWD/tests/.models_cache"
python -c "from faster_whisper import WhisperModel; WhisperModel('tiny', device='cpu', compute_type='int8', download_root='$CYBERSCRIBE_TEST_MODELS_DIR')"
python -m unittest discover -s tests -p "test_*.py" -v
```

Regenerate reference WAV fixtures:

```bash
python tests/fixtures/generate_reference_wavs.py
```

Speech clips are 16 kHz mono trims from the Silero VAD project test WAV (MIT). `silence_only.wav` is synthetic PCM.

Optional strict transcript checks (compare SHA256 of normalized text in memory — never logged):

```bash
export CYBERSCRIBE_STRICT_TRANSCRIPT_TESTS=1
export CYBERSCRIBE_IMMEDIATE_TEXT_SHA256="<sha256>"
export CYBERSCRIBE_PAUSE_TEXT_SHA256="<sha256>"
```

## Latency bench

Measures time from simulated capture finalization through transcription and optional paste sleep. **Only durations and metadata are printed.**

```bash
python bench_dictation_latency.py --iterations 3 --profiles fast,balanced,accurate --json
```

Requires the same offline `tiny` cache as dictation tests.

### In-app timing log (optional)

Set in `config.json`:

```json
"log_pipeline_timings": true
```

When enabled, `debug_CyberScribe.log` receives one line per dictation with `finalize_s`, `transcribe_s`, `paste_s`, `total_s`, profile, device, model size, audio length, and character count — **never the transcribed text**.

## Privacy

Tests and bench output must not print or write dictated content. Assertions may compare transcript text in memory only.
