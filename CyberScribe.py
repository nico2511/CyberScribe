"""
# ==================================================================================
# CyberScribe - Installation & Compilation Instructions
# ==================================================================================
#
# 1. INSTALLATION DES DÉPENDANCES
#    pip install -r requirements.txt
#
# 2. LANCEMENT
#    python CyberScribe.py
#
# 3. COMPILATION EN .EXE (Mode Autonome)
#    pyinstaller --noconsole --onefile --noconfirm --icon="app.ico" --hidden-import=pyaudio --hidden-import=pynput.keyboard._win32 --hidden-import=pynput.mouse._win32 --add-data "<venv>/Lib/site-packages/faster_whisper/assets;faster_whisper/assets" --name "CyberScribe" CyberScribe.py
#
# ==================================================================================
"""

import sys
import os
import time
import json
import threading
import subprocess
import wave
import tempfile
import base64
import queue
import logging
import glob
import ctypes
from io import BytesIO
import tkinter as tk
from tkinter import filedialog, ttk, messagebox

__version__ = "1.4.0"
APP_MUTEX_NAME = "Global\\CyberScribeSingleInstance"
ERROR_ALREADY_EXISTS = 183

# Application directory (works for both script and PyInstaller .exe)
if getattr(sys, "frozen", False):
    APP_DIR = os.path.dirname(sys.executable)
else:
    APP_DIR = os.path.dirname(os.path.abspath(__file__))

# Configure Logging (privacy-conscious: no transcription content logged)
LOG_FILE = os.path.join(APP_DIR, "debug_CyberScribe.log")
MAX_LOG_SIZE = 1 * 1024 * 1024  # 1 MB

VALID_LANGUAGES = {
    "auto", "en", "fr", "de", "es", "it", "ja", "zh", "nl", "uk", "pt", "ru",
}
VALID_MODELS = {"tiny", "base", "small", "medium", "large-v3"}
VALID_DEVICES = {"auto", "cpu", "cuda"}
VALID_COMPUTE = {"int8", "int8_float16", "float16", "float32"}
VALID_PROFILES = {"fast", "balanced", "accurate"}
MAX_RECORD_SECONDS_CAP = 600


def _safe_print(msg):
    """print() raises when stdout is None (PyInstaller --noconsole)."""
    if not sys.stdout:
        return
    try:
        print(msg)
    except Exception:
        pass


def _message_box(title, msg, flags=0x10):
    try:
        ctypes.windll.user32.MessageBoxW(0, str(msg), str(title), flags)
    except Exception:
        _safe_print(f"{title}: {msg}")


def _rotate_log():
    """Purge log file if it exceeds MAX_LOG_SIZE."""
    try:
        if os.path.exists(LOG_FILE) and os.path.getsize(LOG_FILE) > MAX_LOG_SIZE:
            os.remove(LOG_FILE)
    except Exception:
        pass


_rotate_log()

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s",
)


def _cleanup_orphan_temp_wav():
    """Remove leftover CyberScribe wav files from previous runs."""
    try:
        temp_dir = tempfile.gettempdir()
        for path in glob.glob(os.path.join(temp_dir, "cyberscribe_*.wav")):
            try:
                os.remove(path)
            except Exception:
                pass
    except Exception:
        pass


_cleanup_orphan_temp_wav()


def log(msg):
    _safe_print(msg)
    logging.info(msg)


def log_error(msg):
    _safe_print(f"ERROR: {msg}")
    logging.error(msg)


def _acquire_single_instance():
    """Return a live mutex handle, or None if another instance is already running."""
    if sys.platform != "win32":
        return True
    try:
        handle = ctypes.windll.kernel32.CreateMutexW(None, False, APP_MUTEX_NAME)
        if ctypes.windll.kernel32.GetLastError() == ERROR_ALREADY_EXISTS:
            return None
        return handle
    except Exception as e:
        log_error(f"Single-instance mutex failed: {e}")
        return True


# Third-party imports
try:
    import pyaudio
    import pystray
    import pyperclip
    import pyautogui
    from pynput import keyboard
    from PIL import Image
    from faster_whisper import WhisperModel
except ImportError as e:
    _message_box(
        "Erreur CyberScribe",
        f"Erreur critique - Dépendance manquante :\n{e}\n\nL'application va fermer.",
    )
    sys.exit(1)

try:
    from models_storage import (
        canonical_models_dir_config,
        directory_has_model_files,
        ensure_models_dir,
        migrate_models_directory,
        resolve_models_dir,
    )
except ImportError:
    def resolve_models_dir(app_dir, models_dir_config=None):
        return os.path.normpath(os.path.join(app_dir, "models"))

    def ensure_models_dir(path):
        os.makedirs(path, exist_ok=True)
        return path

    def canonical_models_dir_config(resolved_path, app_dir):
        return resolved_path

    def directory_has_model_files(path):
        return False

    def migrate_models_directory(source_dir, dest_dir, move=True):
        return False, "models_storage unavailable"

try:
    from updater import (
        check_for_update,
        cleanup_staging,
        download_release_exe,
        is_frozen_build,
        launch_apply_and_exit,
    )
except ImportError:
    check_for_update = None
    download_release_exe = None
    launch_apply_and_exit = None
    cleanup_staging = None

    def is_frozen_build():
        return bool(getattr(sys, "frozen", False))

# ==================================================================================
# ASSETS (BASE64)
# ==================================================================================

ICON_GRAY_B64 = "iVBORw0KGgoAAAANSUhEUgAAAEAAAABACAYAAACqaXHeAAABZUlEQVR4nO2aQU7DMBBF/3z5BhygYglk3zvkwL0D+wBL1ANwhqBsEAptQ51Jxsn32zlSZv6f2K4rD1DRxoLz99FaLNT4ZfuraiKi6CfGOy5Af9Xs33mx4xlQCIQ4DMhpV7c5U9oEbWIcJEPuHECUQdiHIMQhxCHEMYcYQYdYHx+2ceOz/dhc823bIprT6ZTtyTLy9V3X/QyapgktwmB+rOceX9zBtJ+lkxDH7q3qMN1/r7nS9oCRvkl/KSdhCaa99BDiEOIkx9/fTS6DNDfx4emIaM4fr9nvEuIkr0Dn99tf4fB8LCLmGEIcQhxCHEKc5BXIY0NaI+YYQpwUeQjZfAHawv4V5kCIQ4hDiEOIQ4hD74Bvn1+LP/OEEIcQhxCHEIcQhxAn5bxU+t3gUgWw4YL00n18gf0B/774pbegl8eHxZ95wo11lrrrtMwE0j1CJbfLrNYlVlohtrI0K5VKpVKpoBy+ARvfX7NWpnceAAAAAElFTkSuQmCC"
ICON_RED_B64 = "iVBORw0KGgoAAAANSUhEUgAAAEAAAABACAYAAACqaXHeAAABgklEQVR4nO3asU7DMBQF0Osrd2RipBJLF6TszEz8CQMfxMCfdGJmj8TSBamMTIwdgiJVVYhaoM5LbOf6bHEV+73X2E1lA4U2F3n8JnYsLmbiu5fVoWFxt4kSExFJN/lj13MuQHMq2X17d1rM9wlIBSGOEcZ0nQXvh327xiK46BXhVFHG5iD+HkCkIdoXQYgjxBHinEEfk765WefhMk98cD5uaPLr5RKx3W+3wTm5gPGauq4PF1VVRS1Cm3w/nnPy4gwe+0FxEuLcuVVtH/funEttDejF92d+PmTAFJK2iocQR4jzhr+/WU4DP3Tg65tbxPb+9hp8LyHOW3W0efr89fPV42USffYR4ghxhDhCnLfqyGJBmqLPPkKcj/kSkn0B1on9KwxBiCPEEeIIcYQ4Wnf4cHE1epslQhwhjhBHiCPEEeJ8yE2p7w2OVQDXbpAe249P8HzAvzd+aR3Q89fH6G2WmNnJUvM4XeAA0meEUj4uM9kpsdQKkcvULIqiKIoC6fgG3mJqG3dSmdYAAAAASUVORK5CYII="


def get_icon_image(b64_str):
    return Image.open(BytesIO(base64.b64decode(b64_str)))


# ==================================================================================
# UI COMPONENTS
# ==================================================================================

class PartialOverlay:
    """A high-tech, semi-transparent floating UI shown while recording."""

    def __init__(self, master):
        self.master = master
        self.window = None
        self.indicator = None
        self.active = False
        self.pulse_state = 0

    def show(self):
        if self.window:
            return
        self.window = tk.Toplevel(self.master)
        self.window.overrideredirect(True)
        self.window.attributes("-topmost", True)
        self.window.attributes("-alpha", 0.9)

        BG_COLOR = "#0b1120"
        ACCENT_COLOR = "#00f2ff"

        self.window.config(bg=ACCENT_COLOR)

        screen_w = self.window.winfo_screenwidth()
        screen_h = self.window.winfo_screenheight()
        w, h = 220, 45
        x = (screen_w - w) // 2
        y = screen_h - h - 50
        self.window.geometry(f"{w}x{h}+{x}+{y}")

        inner_frame = tk.Frame(self.window, bg=BG_COLOR)
        inner_frame.pack(fill="both", expand=True, padx=1, pady=1)

        self.indicator = tk.Label(
            inner_frame, text="●", fg="#ff004c", bg=BG_COLOR, font=("Arial", 14, "bold")
        )
        self.indicator.pack(side="left", padx=(15, 5))

        tk.Label(
            inner_frame,
            text="Enregistrement...",
            fg=ACCENT_COLOR,
            bg=BG_COLOR,
            font=("Segoe UI Semibold", 10),
        ).pack(side="left", padx=(0, 15))

        self.active = True
        self._animate_pulse()

    def _animate_pulse(self):
        if not self.active or not self.window:
            return
        colors = ["#ff004c", "#7f1d1d", "#ff004c", "#991b1b"]
        self.pulse_state = (self.pulse_state + 1) % len(colors)
        try:
            self.indicator.config(fg=colors[self.pulse_state])
            self.window.after(500, self._animate_pulse)
        except Exception:
            pass

    def hide(self):
        self.active = False
        if self.window:
            try:
                self.window.destroy()
            except Exception:
                pass
            self.window = None
            self.indicator = None


# ==================================================================================
# CONFIGURATION
# ==================================================================================

CONFIG_FILE = os.path.join(APP_DIR, "config.json")
DEFAULT_CONFIG = {
    "hotkey": "F8",
    "language": "fr",
    "model_size": "base",
    "device": "auto",
    "compute_type": "int8",
    "transcription_profile": "fast",
    "max_record_seconds": 25,
    "check_updates": True,
    "models_dir": "",
}
ALLOWED_KEYS = set(DEFAULT_CONFIG.keys())

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

HOTKEY_MODIFIERS = {
    "ctrl": "<ctrl>",
    "control": "<ctrl>",
    "alt": "<alt>",
    "shift": "<shift>",
    "cmd": "<cmd>",
    "win": "<cmd>",
}


def format_hotkey(raw):
    """Convert a user hotkey like 'F8' or 'ctrl+shift+f8' to pynput form."""
    raw = (raw or "F8").strip()
    parts = [p.strip().lower() for p in raw.replace(" ", "").split("+") if p.strip()]
    if not parts:
        parts = ["f8"]
    formatted = []
    for part in parts:
        part = part.strip("<>")
        if part in HOTKEY_MODIFIERS:
            formatted.append(HOTKEY_MODIFIERS[part])
        elif len(part) == 1:
            formatted.append(part)
        else:
            formatted.append(f"<{part}>")
    return "+".join(formatted)


def sanitize_config(data):
    """Keep only known keys and coerce values to safe defaults."""
    if not isinstance(data, dict):
        return DEFAULT_CONFIG.copy()

    cfg = DEFAULT_CONFIG.copy()
    for key in ALLOWED_KEYS:
        if key not in data:
            continue
        cfg[key] = data[key]

    hotkey = str(cfg.get("hotkey") or "").strip()
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

    check_updates = cfg.get("check_updates")
    if isinstance(check_updates, bool):
        cfg["check_updates"] = check_updates
    elif isinstance(check_updates, str):
        cfg["check_updates"] = check_updates.strip().lower() in ("1", "true", "yes", "on")
    else:
        cfg["check_updates"] = bool(DEFAULT_CONFIG["check_updates"])

    models_dir = cfg.get("models_dir")
    if models_dir is None:
        cfg["models_dir"] = ""
    else:
        cfg["models_dir"] = str(models_dir).strip()[:512]
    return cfg


def detect_nvidia_gpu():
    """Best-effort NVIDIA detection without hard dependency on torch."""
    try:
        result = subprocess.run(
            ["nvidia-smi", "-L"],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
        return result.returncode == 0 and "GPU" in result.stdout
    except Exception:
        return False


class ConfigManager:
    def __init__(self):
        self.config = DEFAULT_CONFIG.copy()
        self.load()

    def load(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.config = sanitize_config(data)
            except Exception as e:
                log_error(f"Erreur chargement config: {e}")
                self.config = DEFAULT_CONFIG.copy()
        else:
            self.save()

    def save(self):
        self.config = sanitize_config(self.config)
        tmp_path = CONFIG_FILE + ".tmp"
        try:
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=4)
            os.replace(tmp_path, CONFIG_FILE)
        except Exception as e:
            log_error(f"Erreur sauvegarde config: {e}")
            try:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except Exception:
                pass

    def get(self, key):
        val = self.config.get(key)
        if key == "models_dir":
            return val if val is not None else ""
        if val is None or val == "":
            return DEFAULT_CONFIG.get(key)
        return val

    def get_models_dir(self):
        return ensure_models_dir(resolve_models_dir(APP_DIR, self.get("models_dir")))

    def set(self, key, value):
        self.config[key] = value
        self.save()

    def update(self, values):
        self.config.update(values)
        self.save()


# ==================================================================================
# AUDIO RECORDER
# ==================================================================================

class AudioRecorder:
    def __init__(self):
        self.audio = pyaudio.PyAudio()
        self.stream = None
        self.frames = []
        self.is_recording = False
        self.format = pyaudio.paInt16
        self.channels = 1
        self.rate = 16000
        self.chunk = 1024
        self._lock = threading.Lock()
        self._temp_files = []

    def start(self):
        if self.is_recording:
            return True
        with self._lock:
            self.frames = []
        self.is_recording = True
        try:
            self.stream = self.audio.open(
                format=self.format,
                channels=self.channels,
                rate=self.rate,
                input=True,
                frames_per_buffer=self.chunk,
            )
            threading.Thread(target=self._record_loop, daemon=True).start()
            log("Recording started...")
            return True
        except Exception as e:
            log_error(f"Error starting recording: {e}")
            self.is_recording = False
            self.stream = None
            return False

    def _record_loop(self):
        while self.is_recording and self.stream:
            try:
                data = self.stream.read(self.chunk, exception_on_overflow=False)
                with self._lock:
                    self.frames.append(data)
            except Exception:
                break

    def _write_wav(self, frames):
        if not frames:
            return None
        fd, path = tempfile.mkstemp(suffix=".wav", prefix="cyberscribe_")
        os.close(fd)
        self._temp_files.append(path)
        try:
            with wave.open(path, "wb") as wf:
                wf.setnchannels(self.channels)
                wf.setsampwidth(self.audio.get_sample_size(self.format))
                wf.setframerate(self.rate)
                wf.writeframes(b"".join(frames))
            return path
        except Exception as e:
            log_error(f"Error saving wav: {e}")
            self._safe_remove(path)
            return None

    def stop(self):
        if not self.is_recording:
            return None
        self.is_recording = False
        log("Recording stopped...")
        try:
            if self.stream:
                self.stream.stop_stream()
                self.stream.close()
                self.stream = None
        except Exception as e:
            log_error(f"Error closing stream: {e}")

        with self._lock:
            frames = list(self.frames)
            self.frames = []
        return self._write_wav(frames)

    def cleanup_temps(self, keep=None):
        keep = keep or set()
        remaining = []
        for path in self._temp_files:
            if path in keep:
                remaining.append(path)
                continue
            self._safe_remove(path)
        self._temp_files = remaining

    @staticmethod
    def _safe_remove(path):
        try:
            if path and os.path.exists(path):
                os.remove(path)
        except Exception:
            pass

    def terminate(self):
        self.is_recording = False
        self.cleanup_temps()
        try:
            self.audio.terminate()
        except Exception:
            pass


# ==================================================================================
# WHISPER TRANSCRIBER
# ==================================================================================

class Transcriber:
    def __init__(self, config):
        self.config = config
        self.model = None
        self.loading = False
        self.loaded_event = threading.Event()
        self._transcribe_lock = threading.Lock()
        threading.Thread(target=self._load_model, daemon=True).start()

    def _load_model(self):
        self.loading = True
        try:
            model_size = self.config.get("model_size")
            device_pref = (self.config.get("device") or "auto").lower()
            compute_pref = (self.config.get("compute_type") or "int8").lower()
            has_nvidia = detect_nvidia_gpu()

            if device_pref == "auto":
                device = "cuda" if has_nvidia else "cpu"
            else:
                device = device_pref

            if device == "cuda" and not has_nvidia:
                log_error("CUDA selected but no NVIDIA GPU detected. Falling back to CPU.")
                device = "cpu"

            if device == "cuda":
                compute_type = "int8_float16" if compute_pref == "int8" else compute_pref
            else:
                compute_type = "int8" if compute_pref in ("int8_float16", "float16") else compute_pref

            models_dir = self.config.get_models_dir()
            log(f"Loading Whisper Model ({model_size}) on {device} ({compute_type})...")
            log(f"Model storage: {models_dir}")
            self.model = WhisperModel(
                model_size, device=device, compute_type=compute_type, download_root=models_dir
            )
            log("Model loaded successfully.")
        except Exception as e:
            log_error(f"Error loading model: {e}")
            self.model = None
        finally:
            self.loaded_event.set()
            self.loading = False

    def reload(self):
        """Reload Whisper after model/device/compute settings change."""
        def _reload():
            with self._transcribe_lock:
                self.model = None
                self.loaded_event.clear()
                self._load_model()

        threading.Thread(target=_reload, daemon=True).start()

    def transcribe(self, audio_path):
        if not self.model:
            if not self.loading and not self.loaded_event.is_set():
                log_error("Model not initialized.")
                return None

            log("Model not ready. Waiting for load to complete...")
            if not self.loaded_event.wait(timeout=120):
                log_error("Timeout waiting for model load.")
                return None

            if not self.model:
                log_error("Model failed to load.")
                return None

        with self._transcribe_lock:
            try:
                log("Starting transcription...")
                lang = self.config.get("language")
                if lang == "auto":
                    lang = None
                profile = self.config.get("transcription_profile") or "fast"
                preset = PROFILE_PRESETS.get(profile, PROFILE_PRESETS["fast"])

                segments, _info = self.model.transcribe(
                    audio_path,
                    beam_size=preset["beam_size"],
                    best_of=preset["best_of"],
                    language=lang,
                    condition_on_previous_text=preset["condition_on_previous_text"],
                    vad_filter=preset["vad_filter"],
                    vad_parameters=preset["vad_parameters"],
                    no_speech_threshold=preset["no_speech_threshold"],
                    log_prob_threshold=preset["log_prob_threshold"],
                )
                text_result = "".join([segment.text for segment in segments]).strip()
                log(f"Transcription finished. ({len(text_result)} chars)")
                return text_result
            except Exception as e:
                log_error(f"Transcription error: {e}")
                return None


# ==================================================================================
# MAIN APPLICATION
# ==================================================================================

class CyberScribeApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.withdraw()
        self.root.title("CyberScribe")

        self.config = ConfigManager()
        self.recorder = AudioRecorder()
        self.transcriber = Transcriber(self.config)
        self.is_recording = False
        self.auto_stop_timer = None
        self._running = True

        self.overlay = PartialOverlay(self.root)
        self.settings_window = None

        self.icon_gray = get_icon_image(ICON_GRAY_B64)
        self.icon_red = get_icon_image(ICON_RED_B64)

        self.tray_icon = None
        self.queue = queue.Queue()
        self.hotkey_listener = None

        self._update_checking = False
        self._update_downloading = False
        self._pending_update = None
        self._update_progress = None
        self._quit_for_update = False

        ensure_models_dir(self.config.get_models_dir())

        self.setup_hotkey()
        if check_for_update and self.config.get("check_updates"):
            threading.Thread(target=self._background_update_check, daemon=True).start()

    def setup_hotkey(self):
        if self.hotkey_listener:
            try:
                self.hotkey_listener.stop()
            except Exception:
                pass
            self.hotkey_listener = None

        raw_hotkey = self.config.get("hotkey")
        formatted_hotkey = format_hotkey(raw_hotkey)
        log(f"Setting up hotkey: {raw_hotkey} -> {formatted_hotkey}")

        try:
            self.hotkey_listener = keyboard.GlobalHotKeys({
                formatted_hotkey: self.on_hotkey_press
            })
            self.hotkey_listener.start()
            log("Hotkey listener started.")
            return True
        except Exception as e:
            log_error(f"Error setting hotkey with pynput: {e}")
            if formatted_hotkey != "<f8>":
                log("Falling back to F8.")
                self.config.set("hotkey", "F8")
                return self.setup_hotkey()
            return False

    def on_hotkey_press(self):
        log("Hotkey detected!")
        self.queue.put("toggle_recording")

    def toggle_recording(self):
        if self.is_recording:
            self.stop_recording_action()
        else:
            self.start_recording_action()

    def _beep(self, freq, duration):
        try:
            import winsound
            winsound.Beep(freq, duration)
        except Exception:
            pass

    def _notify(self, title, message):
        if not self.tray_icon:
            return
        try:
            self.tray_icon.notify(message, title)
        except Exception:
            pass

    def start_recording_action(self):
        log("Action: Start Recording")
        if not self.recorder.start():
            self.is_recording = False
            self.update_tray_icon(recording=False)
            self._notify("CyberScribe", "Impossible d'accéder au microphone.")
            return

        self.is_recording = True
        self.update_tray_icon(recording=True)
        self._beep(600, 200)
        self.overlay.show()

        max_seconds = self.config.get("max_record_seconds")
        try:
            max_seconds = int(max_seconds)
        except Exception:
            max_seconds = 0

        if max_seconds > 0:
            if self.auto_stop_timer:
                self.auto_stop_timer.cancel()
            self.auto_stop_timer = threading.Timer(
                max_seconds, lambda: self.queue.put("auto_stop_recording")
            )
            self.auto_stop_timer.daemon = True
            self.auto_stop_timer.start()
            log(f"Auto-stop armed at {max_seconds}s.")

    def stop_recording_action(self):
        log("Action: Stop Recording")
        self.is_recording = False
        self.update_tray_icon(recording=False)

        if self.auto_stop_timer:
            self.auto_stop_timer.cancel()
            self.auto_stop_timer = None

        self.overlay.hide()
        self._beep(400, 200)

        audio_path = self.recorder.stop()
        if audio_path:
            log("Audio captured.")
            threading.Thread(target=self.process_audio, args=(audio_path,), daemon=True).start()

    def update_tray_icon(self, recording=False, loading=False):
        if not self.tray_icon:
            return
        try:
            if loading:
                self.tray_icon.icon = self.icon_gray
                self.tray_icon.title = "CyberScribe - Chargement du modèle..."
            elif recording:
                self.tray_icon.icon = self.icon_red
                self.tray_icon.title = "CyberScribe - Enregistrement..."
            else:
                self.tray_icon.icon = self.icon_gray
                self.tray_icon.title = f"CyberScribe v{__version__} - Prêt"
        except Exception as e:
            log_error(f"Error updating tray: {e}")

    def process_audio(self, audio_path):
        log("Transcribing...")
        try:
            text = self.transcriber.transcribe(audio_path)
        finally:
            self.recorder._safe_remove(audio_path)

        if text:
            log(f"Transcription result: [Redacted for security] ({len(text)} chars)")
            self.paste_text(text)
        else:
            log("No transcription result.")
            self._notify("CyberScribe", "Aucune transcription. Vérifiez le micro ou les logs.")

    def paste_text(self, text):
        try:
            log("Attempting to paste text...")
            pyperclip.copy(text)
            time.sleep(0.3)

            from pynput.keyboard import Controller, Key
            keyboard_controller = Controller()

            with keyboard_controller.pressed(Key.ctrl):
                keyboard_controller.press("v")
                keyboard_controller.release("v")

            log("Paste command sent.")
        except Exception as e:
            log_error(f"Error pasting text: {e}")
            try:
                log("Retrying with pyautogui...")
                pyautogui.hotkey("ctrl", "v")
            except Exception as e2:
                log_error(f"Fallback paste failed: {e2}")

    def request_settings(self, icon, item):
        self.queue.put("settings")

    def request_quit(self, icon, item):
        self.queue.put("quit")

    def request_check_updates(self, icon, item):
        self.queue.put("check_updates")

    def _background_update_check(self):
        if self._update_checking or not check_for_update:
            return
        self._update_checking = True
        try:
            time.sleep(8)
            if not self._running:
                return
            result = check_for_update(__version__)
            if result.update_available and result.latest:
                self._pending_update = result.latest
                self.queue.put(("update_available", result.latest.version))
        except Exception as e:
            log_error(f"Background update check: {e}")
        finally:
            self._update_checking = False

    def _manual_update_check(self):
        if not check_for_update:
            messagebox.showinfo(
                "CyberScribe",
                "Le module de mise à jour n'est pas disponible dans cette installation.",
                parent=self.root,
            )
            return
        if self._update_checking:
            messagebox.showinfo("CyberScribe", "Vérification déjà en cours…", parent=self.root)
            return

        def _work():
            self._update_checking = True
            try:
                result = check_for_update(__version__)
                self.queue.put(("update_check_done", result))
            finally:
                self._update_checking = False

        threading.Thread(target=_work, daemon=True).start()
        self._notify("CyberScribe", "Recherche de mises à jour sur GitHub…")

    def _show_update_check_result(self, result):
        if not result.ok:
            messagebox.showwarning(
                "CyberScribe",
                f"Impossible de vérifier les mises à jour.\n{result.error or 'Erreur inconnue'}",
                parent=self.root,
            )
            return
        if not result.update_available or not result.latest:
            messagebox.showinfo(
                "CyberScribe",
                f"Vous utilisez la dernière version ({__version__}).",
                parent=self.root,
            )
            return
        self._pending_update = result.latest
        self._prompt_install_update(result.latest.version)

    def _prompt_install_update(self, new_version):
        if not is_frozen_build():
            messagebox.showinfo(
                "CyberScribe",
                f"Version {new_version} disponible sur GitHub.\n"
                "La mise à jour automatique s'applique uniquement à l'exécutable Windows (CyberScribe.exe).",
                parent=self.root,
            )
            return
        answer = messagebox.askyesno(
            "CyberScribe — mise à jour",
            f"La version {new_version} est disponible (vous êtes en {__version__}).\n\n"
            "Télécharger et installer maintenant ?\n"
            "L'application redémarrera après la mise à jour.",
            parent=self.root,
        )
        if answer:
            self._start_update_download()

    def _start_update_download(self):
        release = self._pending_update
        if not release or not download_release_exe:
            return
        if self._update_downloading:
            return
        self._update_downloading = True
        self._update_progress = {"done": 0, "total": release.exe_size}
        self._notify("CyberScribe", f"Téléchargement de la v{release.version}…")
        self.update_tray_icon(loading=True)

        def _work():
            try:
                def on_progress(done, total):
                    self._update_progress = {"done": done, "total": total}

                path = download_release_exe(release, APP_DIR, __version__, progress=on_progress)
                self.queue.put(("update_downloaded", path, release.version))
            except Exception as e:
                log_error(f"Update download failed: {e}")
                self.queue.put(("update_download_failed", str(e)))
            finally:
                self._update_downloading = False

        threading.Thread(target=_work, daemon=True).start()

    def _finish_update_download(self, staging_path, new_version):
        self.update_tray_icon(loading=False)
        if not os.path.isfile(staging_path):
            messagebox.showerror(
                "CyberScribe",
                "Fichier de mise à jour introuvable après téléchargement.",
                parent=self.root,
            )
            return
        answer = messagebox.askyesno(
            "CyberScribe — mise à jour",
            f"Téléchargement terminé (v{new_version}).\n"
            "Installer maintenant et redémarrer CyberScribe ?",
            parent=self.root,
        )
        if not answer:
            return
        try:
            exe_name = os.path.basename(sys.executable)
            launch_apply_and_exit(APP_DIR, exe_name)
            self._quit_for_update = True
            self.queue.put("quit")
        except Exception as e:
            log_error(f"Could not launch update script: {e}")
            messagebox.showerror(
                "CyberScribe",
                f"Échec du lancement de la mise à jour :\n{e}",
                parent=self.root,
            )

    def open_settings_window(self):
        if self.settings_window and self.settings_window.winfo_exists():
            try:
                self.settings_window.lift()
                self.settings_window.focus_force()
                return
            except Exception:
                pass

        try:
            self.settings_window = tk.Toplevel(self.root)
            root = self.settings_window
            root.title(f"CyberScribe Config v{__version__}")

            C_BG = "#0f172a"
            C_ACCENT = "#06b6d4"
            C_INPUT_BG = "#1e293b"
            C_INPUT_FG = "#38bdf8"
            C_WARN = "#f43f5e"

            root.configure(bg=C_ACCENT)

            width = 480
            ws, hs = root.winfo_screenwidth(), root.winfo_screenheight()
            height = min(720, max(480, hs - 100))
            x = (ws // 2) - (width // 2)
            y = max(20, (hs // 2) - (height // 2))
            root.geometry(f"{width}x{height}+{x}+{y}")
            root.minsize(420, 420)

            root.attributes("-topmost", True)
            root.after(100, lambda: root.attributes("-topmost", False))

            outer = tk.Frame(root, bg=C_BG)
            outer.pack(fill="both", expand=True, padx=2, pady=2)

            canvas = tk.Canvas(outer, bg=C_BG, highlightthickness=0)
            scrollbar = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
            main_frame = tk.Frame(canvas, bg=C_BG)

            main_frame.bind(
                "<Configure>",
                lambda e: canvas.configure(scrollregion=canvas.bbox("all")),
            )
            canvas_window = canvas.create_window((0, 0), window=main_frame, anchor="nw")
            canvas.configure(yscrollcommand=scrollbar.set)

            def _sync_width(event):
                canvas.itemconfigure(canvas_window, width=event.width)

            canvas.bind("<Configure>", _sync_width)

            def _on_mousewheel(event):
                canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
                return "break"

            def _bind_wheel(widget):
                widget.bind("<MouseWheel>", _on_mousewheel)
                for child in widget.winfo_children():
                    _bind_wheel(child)

            canvas.bind("<MouseWheel>", _on_mousewheel)
            root.protocol("WM_DELETE_WINDOW", root.destroy)

            canvas.pack(side="left", fill="both", expand=True)
            scrollbar.pack(side="right", fill="y")

            style = ttk.Style(root)
            style.theme_use("clam")
            style.configure(
                "TCombobox",
                fieldbackground=C_INPUT_BG,
                background=C_INPUT_BG,
                foreground=C_INPUT_FG,
                arrowcolor=C_ACCENT,
            )

            def create_label(text, parent=main_frame):
                return tk.Label(
                    parent, text=text, bg=C_BG, fg=C_ACCENT, font=("Segoe UI", 10, "bold")
                )

            def create_help_text(text, parent=main_frame):
                return tk.Label(
                    parent,
                    text=text,
                    bg=C_BG,
                    fg="#94a3b8",
                    font=("Consolas", 8),
                    justify="left",
                    wraplength=400,
                )

            def create_entry(var, parent=main_frame):
                return tk.Entry(
                    parent,
                    textvariable=var,
                    bg=C_INPUT_BG,
                    fg=C_INPUT_FG,
                    insertbackground=C_ACCENT,
                    font=("Consolas", 11),
                    relief="flat",
                    bd=5,
                )

            tk.Label(
                main_frame,
                text="/// SYSTEM CONFIGURATION",
                bg=C_BG,
                fg=C_ACCENT,
                font=("Consolas", 12, "bold"),
            ).pack(pady=(16, 6))
            tk.Label(
                main_frame,
                text=f"CyberScribe v{__version__}",
                bg=C_BG,
                fg="#94a3b8",
                font=("Consolas", 8),
            ).pack()
            tk.Frame(main_frame, bg=C_ACCENT, height=2).pack(fill="x", padx=20, pady=(8, 12))

            create_label(">> ACTIVATION KEY").pack(pady=(8, 2))
            create_help_text("Key binding for recording (e.g. F8 or ctrl+shift+f8)").pack(pady=(0, 4))
            hk_var = tk.StringVar(root, value=self.config.get("hotkey"))
            create_entry(hk_var).pack(pady=0, ipadx=5, ipady=3)

            create_label(">> LANGUAGE MODULE").pack(pady=(12, 2))
            create_help_text("Target language for vocal processing.").pack(pady=(0, 4))
            lang_var = tk.StringVar(root, value=self.config.get("language") or "auto")
            LANGUAGES = ["auto", "en", "fr", "de", "es", "it", "ja", "zh", "nl", "uk", "pt", "ru"]
            ttk.Combobox(
                main_frame, textvariable=lang_var, values=LANGUAGES, font=("Consolas", 10)
            ).pack(pady=0)

            create_label(">> NEURAL MODEL").pack(pady=(12, 2))
            create_help_text("Model size: Tiny (Fast) <-> Large (Precise). Reloads on save.").pack(
                pady=(0, 4)
            )
            model_var = tk.StringVar(root, value=self.config.get("model_size"))
            ttk.Combobox(
                main_frame,
                textvariable=model_var,
                values=["tiny", "base", "small", "medium", "large-v3"],
                font=("Consolas", 10),
            ).pack(pady=0)

            create_label(">> PROCESSING UNIT").pack(pady=(12, 2))
            create_help_text("Compute device: CPU (Universal) / CUDA (GPU)").pack(pady=(0, 4))
            device_var = tk.StringVar(root, value=self.config.get("device"))
            ttk.Combobox(
                main_frame, textvariable=device_var, values=["auto", "cpu", "cuda"], font=("Consolas", 10)
            ).pack(pady=0)

            create_label(">> COMPUTE TYPE").pack(pady=(12, 2))
            create_help_text("Precision: int8 (fast) / float16 (GPU) / float32 (quality)").pack(
                pady=(0, 4)
            )
            compute_var = tk.StringVar(root, value=self.config.get("compute_type") or "int8")
            ttk.Combobox(
                main_frame,
                textvariable=compute_var,
                values=["int8", "int8_float16", "float16", "float32"],
                font=("Consolas", 10),
            ).pack(pady=0)

            create_label(">> TRANSCRIPTION PROFILE").pack(pady=(12, 2))
            create_help_text("fast = low latency, balanced = compromise, accurate = quality").pack(
                pady=(0, 4)
            )
            profile_var = tk.StringVar(root, value=self.config.get("transcription_profile") or "fast")
            ttk.Combobox(
                main_frame,
                textvariable=profile_var,
                values=["fast", "balanced", "accurate"],
                font=("Consolas", 10),
            ).pack(pady=0)

            create_label(">> MAX RECORD DURATION (SECONDS)").pack(pady=(12, 2))
            create_help_text("Auto-stop safety. 0 disables limit. Recommended: 15-30s").pack(
                pady=(0, 4)
            )
            max_record_var = tk.StringVar(root, value=str(self.config.get("max_record_seconds") or 25))
            create_entry(max_record_var).pack(pady=0, ipadx=5, ipady=3)

            create_label(">> SOFTWARE UPDATES").pack(pady=(12, 2))
            create_help_text(
                "Vérifie GitHub Releases pour CyberScribe.exe (connexion Internet requise)."
            ).pack(pady=(0, 4))
            check_updates_var = tk.BooleanVar(
                root, value=bool(self.config.get("check_updates"))
            )

            def _toggle_check_updates():
                self.config.set("check_updates", bool(check_updates_var.get()))

            tk.Checkbutton(
                main_frame,
                text="Vérifier automatiquement au démarrage",
                variable=check_updates_var,
                command=_toggle_check_updates,
                bg=C_BG,
                fg="#e2e8f0",
                selectcolor=C_INPUT_BG,
                activebackground=C_BG,
                activeforeground="#e2e8f0",
                font=("Consolas", 9),
            ).pack(anchor="w", padx=30)

            def _check_updates_ui():
                self._manual_update_check()

            tk.Button(
                main_frame,
                text="[ VÉRIFIER LES MISES À JOUR ]",
                command=_check_updates_ui,
                bg="#334155",
                fg="white",
                font=("Consolas", 9, "bold"),
                relief="flat",
            ).pack(pady=(8, 4), ipadx=8)

            create_label(">> MODEL STORAGE").pack(pady=(12, 2))
            create_help_text(
                "Dossier des modèles Whisper. Vide = dossier « models » à côté de l'application."
            ).pack(pady=(0, 4))
            path_var = tk.StringVar(root, value=self.config.get_models_dir())

            models_row = tk.Frame(main_frame, bg=C_BG)
            models_row.pack(fill="x", padx=30, pady=(0, 4))
            models_entry = create_entry(path_var, parent=models_row)
            models_entry.pack(side="left", fill="x", expand=True, ipadx=3, ipady=2)

            def _browse_models():
                initial = path_var.get().strip() or self.config.get_models_dir()
                chosen = filedialog.askdirectory(
                    parent=root,
                    title="Dossier des modèles Whisper",
                    initialdir=initial if os.path.isdir(initial) else APP_DIR,
                )
                if chosen:
                    path_var.set(os.path.normpath(chosen))

            tk.Button(
                models_row,
                text="…",
                command=_browse_models,
                bg=C_INPUT_BG,
                fg=C_ACCENT,
                font=("Consolas", 10, "bold"),
                relief="flat",
                width=3,
            ).pack(side="left", padx=(6, 0))

            def test_rec():
                self.queue.put("toggle_recording")

            tk.Button(
                main_frame,
                text="[ INITIATE SELF-TEST ]",
                command=test_rec,
                bg=C_WARN,
                fg="white",
                font=("Consolas", 9, "bold"),
                relief="flat",
            ).pack(pady=(24, 5), ipadx=10)

            def save():
                old_model = self.config.get("model_size")
                old_device = self.config.get("device")
                old_compute = self.config.get("compute_type")
                old_models_resolved = self.config.get_models_dir()

                try:
                    max_record = int(max_record_var.get())
                except Exception:
                    max_record = DEFAULT_CONFIG["max_record_seconds"]

                new_models_input = path_var.get().strip()
                new_models_resolved = resolve_models_dir(
                    APP_DIR, new_models_input if new_models_input else None
                )
                models_cfg = canonical_models_dir_config(new_models_resolved, APP_DIR)

                if (
                    os.path.normcase(new_models_resolved) != os.path.normcase(old_models_resolved)
                    and directory_has_model_files(old_models_resolved)
                ):
                    choice = messagebox.askyesnocancel(
                        "CyberScribe — modèles",
                        "Le dossier des modèles change.\n\n"
                        "Déplacer les fichiers existants vers le nouveau dossier ?\n\n"
                        "Oui = déplacer\nNon = copier\nAnnuler = garder l'ancien dossier",
                        parent=root,
                    )
                    if choice is None:
                        return
                    ok, migrate_msg = migrate_models_directory(
                        old_models_resolved,
                        new_models_resolved,
                        move=bool(choice),
                    )
                    if not ok:
                        messagebox.showerror(
                            "CyberScribe",
                            f"Migration des modèles impossible :\n{migrate_msg}",
                            parent=root,
                        )
                        return
                    log(migrate_msg)
                else:
                    try:
                        ensure_models_dir(new_models_resolved)
                    except OSError as e:
                        messagebox.showerror(
                            "CyberScribe",
                            f"Impossible de créer le dossier des modèles :\n{e}",
                            parent=root,
                        )
                        return

                self.config.update({
                    "hotkey": hk_var.get(),
                    "language": lang_var.get(),
                    "model_size": model_var.get(),
                    "device": device_var.get(),
                    "compute_type": compute_var.get(),
                    "transcription_profile": profile_var.get() or "fast",
                    "max_record_seconds": max_record,
                    "models_dir": models_cfg,
                })
                if not self.setup_hotkey():
                    messagebox.showwarning(
                        "CyberScribe",
                        "Raccourci invalide. Retour à F8.",
                        parent=root,
                    )

                models_changed = (
                    os.path.normcase(self.config.get_models_dir())
                    != os.path.normcase(old_models_resolved)
                )
                model_changed = (
                    self.config.get("model_size") != old_model
                    or self.config.get("device") != old_device
                    or self.config.get("compute_type") != old_compute
                    or models_changed
                )
                if model_changed:
                    self.transcriber.reload()
                    self.update_tray_icon(loading=True)
                    messagebox.showinfo(
                        "CyberScribe",
                        "Configuration enregistrée.\nLe modèle Whisper se recharge en arrière-plan.",
                        parent=root,
                    )
                else:
                    messagebox.showinfo("CyberScribe", "SYSTEM UPDATED.", parent=root)
                root.destroy()

            tk.Button(
                main_frame,
                text=">> SAVE CONFIGURATION <<",
                command=save,
                bg=C_ACCENT,
                fg="white",
                font=("Consolas", 11, "bold"),
                relief="flat",
            ).pack(pady=(8, 20), ipadx=20, ipady=5)
            _bind_wheel(main_frame)
        except Exception as e:
            log_error(f"GUI Error: {e}")

    def show_splash(self):
        try:
            splash = tk.Toplevel(self.root)
            splash.overrideredirect(True)
            splash.attributes("-topmost", True)
            w, h = 400, 110
            ws, hs = splash.winfo_screenwidth(), splash.winfo_screenheight()
            x, y = (ws / 2) - (w / 2), (hs / 2) - (h / 2)
            splash.geometry(f"{w}x{h}+{int(x)}+{int(y)}")
            frame = tk.Frame(splash, bg="#1f2937", relief="raised", bd=2)
            frame.pack(fill="both", expand=True)
            tk.Label(
                frame,
                text=f"CyberScribe v{__version__}",
                font=("Segoe UI", 16, "bold"),
                bg="#1f2937",
                fg="white",
            ).pack(pady=(18, 4))
            status = (
                "Modèle chargé. Appuyez sur votre raccourci."
                if self.transcriber.model
                else "Chargement du modèle Whisper…"
            )
            tk.Label(
                frame,
                text=status,
                font=("Segoe UI", 10),
                bg="#1f2937",
                fg="#d1d5db",
            ).pack(pady=(0, 18))
            self.root.after(3000, splash.destroy)
        except Exception as e:
            log_error(f"Splash error: {e}")

    def run_tray(self):
        menu_items = [
            pystray.MenuItem("Configuration", self.request_settings),
        ]
        if check_for_update:
            menu_items.append(
                pystray.MenuItem("Vérifier les mises à jour", self.request_check_updates)
            )
        menu_items.append(pystray.MenuItem("Quitter", self.request_quit))
        menu = pystray.Menu(*menu_items)
        self.tray_icon = pystray.Icon(
            "CyberScribe", self.icon_gray, f"CyberScribe v{__version__}", menu
        )
        self.tray_icon.run()

    def run(self):
        log(f"=== Application Started v{__version__} ===")
        self.show_splash()
        tray_thread = threading.Thread(target=self.run_tray, daemon=True)
        tray_thread.start()
        self.update_tray_icon(loading=True)
        while self._running:
            try:
                try:
                    self.root.update()
                except tk.TclError:
                    break

                try:
                    msg = self.queue.get(timeout=0.1)
                except queue.Empty:
                    if self.transcriber.model and not self.transcriber.loading:
                        if not self.is_recording:
                            self.update_tray_icon(loading=False)
                    if not tray_thread.is_alive():
                        break
                    continue
                if msg == "settings":
                    self.open_settings_window()
                elif msg == "toggle_recording":
                    self.toggle_recording()
                elif msg == "auto_stop_recording":
                    if self.is_recording:
                        self.stop_recording_action()
                elif msg == "check_updates":
                    self._manual_update_check()
                elif msg == "quit":
                    break
                elif isinstance(msg, tuple) and msg:
                    if msg[0] == "update_available" and len(msg) > 1:
                        self._notify(
                            "CyberScribe",
                            f"Mise à jour v{msg[1]} disponible — menu ou Configuration.",
                        )
                    elif msg[0] == "update_check_done" and len(msg) > 1:
                        self._show_update_check_result(msg[1])
                    elif msg[0] == "update_downloaded" and len(msg) > 2:
                        self._finish_update_download(msg[1], msg[2])
                    elif msg[0] == "update_download_failed" and len(msg) > 1:
                        self.update_tray_icon(loading=False)
                        self._notify("CyberScribe", "Échec du téléchargement de la mise à jour.")
                        messagebox.showerror(
                            "CyberScribe",
                            f"Téléchargement impossible :\n{msg[1]}",
                            parent=self.root,
                        )
            except KeyboardInterrupt:
                break
        self.stop_app()

    def stop_app(self):
        if not self._running:
            return
        self._running = False
        log("Stopping...")
        if self.is_recording:
            try:
                self.recorder.stop()
            except Exception:
                pass
        if self.auto_stop_timer:
            try:
                self.auto_stop_timer.cancel()
            except Exception:
                pass
            self.auto_stop_timer = None
        try:
            self.overlay.hide()
        except Exception:
            pass
        try:
            self.recorder.terminate()
        except Exception:
            pass
        try:
            if self.hotkey_listener:
                self.hotkey_listener.stop()
        except Exception:
            pass
        try:
            if self.tray_icon:
                self.tray_icon.stop()
        except Exception:
            pass
        try:
            self.root.destroy()
        except Exception:
            pass
        if cleanup_staging and not self._quit_for_update:
            try:
                cleanup_staging(APP_DIR)
            except Exception:
                pass


if __name__ == "__main__":
    instance_handle = _acquire_single_instance()
    if instance_handle is None:
        _message_box(
            "CyberScribe",
            "CyberScribe est déjà en cours d'exécution.",
            0x40,
        )
        sys.exit(0)
    app = CyberScribeApp()
    app.run()
    sys.exit(0)
