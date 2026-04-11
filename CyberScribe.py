"""
# ==================================================================================
# CyberScribe - Installation & Compilation Instructions
# ==================================================================================
#
# 1. INSTALLATION DES DÉPENDANCES
#    pip install faster-whisper pyaudio pystray Pillow pyperclip pyautogui pynput
#
#    Note : Si 'pyaudio' échoue à l'installation, utilisez 'pipwin' :
#    pip install pipwin
#    pipwin install pyaudio
#
# 3. COMPILATION EN .EXE (Mode Autonome)
#    pyinstaller --noconsole --onefile --noconfirm --hidden-import=pyaudio --hidden-import=pynput.keyboard._win32 --hidden-import=pynput.mouse._win32 --name "CyberScribe" CyberScribe.py
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
from io import BytesIO
import tkinter as tk
from tkinter import ttk, messagebox

# Application directory (works for both script and PyInstaller .exe)
if getattr(sys, 'frozen', False):
    APP_DIR = os.path.dirname(sys.executable)
else:
    APP_DIR = os.path.dirname(os.path.abspath(__file__))

MODELS_DIR = os.path.join(APP_DIR, "models")
os.makedirs(MODELS_DIR, exist_ok=True)

# Configure Logging (privacy-conscious: no transcription content logged)
LOG_FILE = os.path.join(APP_DIR, "debug_CyberScribe.log")
MAX_LOG_SIZE = 1 * 1024 * 1024  # 1 MB

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
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def _cleanup_orphan_temp_wav():
    """Remove orphan .wav files from temp directory left by previous crashes."""
    try:
        temp_dir = tempfile.gettempdir()
        for f in glob.glob(os.path.join(temp_dir, "tmp*.wav")):
            try:
                os.remove(f)
            except Exception:
                pass
    except Exception:
        pass

_cleanup_orphan_temp_wav()

def log(msg):
    # Also print to console if available
    print(msg)
    logging.info(msg)

def log_error(msg):
    print(f"ERROR: {msg}")
    logging.error(msg)

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
    import ctypes
    msg = f"Erreur critique - Dépendance manquante :\n{e}\n\nL'application va fermer."
    try:
        ctypes.windll.user32.MessageBoxW(0, msg, "Erreur CyberScribe", 0x10)
    except: pass
    sys.exit(1)

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
    """A floating, semi-transparent window to show live transcription."""
    def __init__(self):
        self.root = None
        self.label = None
        self.active = False

    def show(self):
        if self.root: return
        self.root = tk.Tk()
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.attributes("-alpha", 0.8)
        self.root.config(bg="#1e293b")
        
        # Position at the bottom center of the screen
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        w, h = 600, 60
        x = (screen_w - w) // 2
        y = screen_h - h - 100
        self.root.geometry(f"{w}x{h}+{x}+{y}")

        self.label = tk.Label(
            self.root, 
            text="...", 
            font=("Segoe UI", 12, "italic"), 
            fg="#38bdf8", 
            bg="#1e293b",
            wraplength=580
        )
        self.label.pack(expand=True, fill='both', padx=10, pady=5)
        self.active = True
        
        # Run in a small thread-friendly way
        def _loop():
            if self.active and self.root:
                try:
                    self.root.update()
                    self.root.after(100, _loop)
                except: pass
        
        self.root.after(100, _loop)

    def update_text(self, text):
        if not self.label: return
        # Truncate if too long for preview
        display_text = text if len(text) < 150 else "..." + text[-147:]
        self.label.config(text=display_text)

    def hide(self):
        self.active = False
        if self.root:
            try:
                self.root.destroy()
            except: pass
            self.root = None
            self.label = None

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
    "streaming_preview": True
}

PROFILE_PRESETS = {
    "fast": {
        "beam_size": 1,
        "best_of": 1,
        "vad_filter": True,
        "vad_parameters": {"min_silence_duration_ms": 250},
        "condition_on_previous_text": False,
        "no_speech_threshold": 0.7,
        "log_prob_threshold": -2.0
    },
    "balanced": {
        "beam_size": 3,
        "best_of": 2,
        "vad_filter": True,
        "vad_parameters": {"min_silence_duration_ms": 400},
        "condition_on_previous_text": False,
        "no_speech_threshold": 0.75,
        "log_prob_threshold": -1.5
    },
    "accurate": {
        "beam_size": 5,
        "best_of": 3,
        "vad_filter": True,
        "vad_parameters": {"min_silence_duration_ms": 500},
        "condition_on_previous_text": False,
        "no_speech_threshold": 0.8,
        "log_prob_threshold": -1.0
    }
}

def detect_nvidia_gpu():
    """Best-effort NVIDIA detection without hard dependency on torch."""
    try:
        result = subprocess.run(
            ["nvidia-smi", "-L"],
            capture_output=True,
            text=True,
            timeout=2,
            check=False
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
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.config.update(data)
            except Exception as e:
                log_error(f"Erreur chargement config: {e}")

    def save(self):
        try:
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=4)
        except Exception as e:
            log_error(f"Erreur sauvegarde config: {e}")

    def get(self, key):
        return self.config.get(key, DEFAULT_CONFIG.get(key))

    def set(self, key, value):
        self.config[key] = value
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

    def start(self):
        if self.is_recording:
            return
        self.frames = []
        self.is_recording = True
        try:
            self.stream = self.audio.open(format=self.format, channels=self.channels,
                                          rate=self.rate, input=True,
                                          frames_per_buffer=self.chunk)
            threading.Thread(target=self._record_loop, daemon=True).start()
            log("Recording started...")
        except Exception as e:
            log_error(f"Error starting recording: {e}")
            self.is_recording = False

    def _record_loop(self):
        while self.is_recording and self.stream:
            try:
                data = self.stream.read(self.chunk, exception_on_overflow=False)
                self.frames.append(data)
            except Exception:
                break

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
        
        if not self.frames:
            return None

        fd, path = tempfile.mkstemp(suffix=".wav")
        os.close(fd)
        
        try:
            wf = wave.open(path, 'wb')
            wf.setnchannels(self.channels)
            wf.setsampwidth(self.audio.get_sample_size(self.format))
            wf.setframerate(self.rate)
            wf.writeframes(b''.join(self.frames))
            wf.close()
            return path
        except Exception as e:
            log_error(f"Error saving wav: {e}")
            return None

    def get_current_audio_path(self):
        """Save current frames to a temp file without stopping the stream."""
        if not self.frames:
            return None
        
        # Thread-safe copy of frames
        current_frames = list(self.frames)
        
        fd, path = tempfile.mkstemp(suffix=".wav")
        os.close(fd)
        
        try:
            wf = wave.open(path, 'wb')
            wf.setnchannels(self.channels)
            wf.setsampwidth(self.audio.get_sample_size(self.format))
            wf.setframerate(self.rate)
            wf.writeframes(b''.join(current_frames))
            wf.close()
            return path
        except Exception as e:
            log_error(f"Error saving partial wav: {e}")
            return None

    def terminate(self):
        self.audio.terminate()

# ==================================================================================
# WHISPER TRANSCRIBER
# ==================================================================================

class Transcriber:
    def __init__(self, config):
        self.config = config
        self.model = None
        self.loading = False
        self.loaded_event = threading.Event()
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
                # Good speed/VRAM compromise for many consumer GPUs
                compute_type = "int8_float16" if compute_pref == "int8" else compute_pref
            else:
                compute_type = "int8" if compute_pref in ("int8_float16", "float16") else compute_pref

            log(f"Loading Whisper Model ({model_size}) on {device} ({compute_type})...")
            self.model = WhisperModel(model_size, device=device, compute_type=compute_type, download_root=MODELS_DIR)
            log("Model loaded successfully.")
        except Exception as e:
            log_error(f"Error loading model: {e}")
            self.model = None
        finally:
            self.loaded_event.set()
            self.loading = False

    def transcribe(self, audio_path):
        if not self.model:
            if not self.loading and not self.loaded_event.is_set():
                 # Should not happen if strictly following logic, but safety check
                 return "Erreur: Modèle non initialisé."

            log("Model not ready. Waiting for load to complete...")
            # Wait up to 120 seconds for the model to load
            if not self.loaded_event.wait(timeout=120):
                log_error("Timeout waiting for model load.")
                return "Erreur: Le modèle met trop de temps à charger."
            
            if not self.model:
                log_error("Model failed to load.")
                return "Erreur: Échec du chargement du modèle. Vérifiez les logs."
        
        try:
            log(f"Starting transcription of {audio_path}...")
            lang = self.config.get("language")
            if lang == "auto":
                lang = None
            profile = self.config.get("transcription_profile") or "fast"
            preset = PROFILE_PRESETS.get(profile, PROFILE_PRESETS["fast"])

            segments, info = self.model.transcribe(
                audio_path,
                beam_size=preset["beam_size"],
                best_of=preset["best_of"],
                language=lang,
                condition_on_previous_text=preset["condition_on_previous_text"],
                vad_filter=preset["vad_filter"],
                vad_parameters=preset["vad_parameters"],
                no_speech_threshold=preset["no_speech_threshold"],
                log_prob_threshold=preset["log_prob_threshold"]
            )
            text_result = "".join([segment.text for segment in segments]).strip()
            log(f"Transcription finished. ({len(text_result)} chars)")
            return text_result
        except Exception as e:
            log_error(f"Transcription error: {e}")
            return f"Error during transcription: {e}"

# ==================================================================================
# MAIN APPLICATION
# ==================================================================================

class CyberScribeApp:
    def __init__(self):
        self.config = ConfigManager()
        self.recorder = AudioRecorder()
        self.transcriber = Transcriber(self.config)
        self.is_recording = False
        self.auto_stop_timer = None
        
        self.overlay = PartialOverlay()
        self.streaming_thread = None
        self.last_partial_text = ""
        
        self.icon_gray = get_icon_image(ICON_GRAY_B64)
        self.icon_red = get_icon_image(ICON_RED_B64)
        
        self.tray_icon = None
        self.queue = queue.Queue()
        self.hotkey_listener = None
        
        self.setup_hotkey()

    def setup_hotkey(self):
        # Stop existing listener if any
        if self.hotkey_listener:
            try:
                self.hotkey_listener.stop()
            except: pass
            self.hotkey_listener = None

        raw_hotkey = self.config.get("hotkey")
        log(f"Setting up hotkey: {raw_hotkey}")

        # Pynput format conversion (F8 -> <f8>)
        formatted_hotkey = raw_hotkey.lower()
        if len(formatted_hotkey) > 1 and not formatted_hotkey.startswith('<'):
            formatted_hotkey = f"<{formatted_hotkey}>"
        
        try:
            # Create a GlobalHotKeys listener
            self.hotkey_listener = keyboard.GlobalHotKeys({
                formatted_hotkey: self.on_hotkey_press
            })
            self.hotkey_listener.start()
            log("Hotkey listener started.")
        except Exception as e:
            log_error(f"Error setting hotkey with pynput: {e}")

    def on_hotkey_press(self):
        log("Hotkey detected!")
        self.queue.put("toggle_recording")

    def toggle_recording(self):
        if self.is_recording:
            self.stop_recording_action()
        else:
            self.start_recording_action()

    def start_recording_action(self):
        log("Action: Start Recording")
        self.is_recording = True
        self.update_tray_icon(recording=True)
        
        try:
            import winsound
            winsound.Beep(600, 200)
        except: pass

        self.recorder.start()
        
        if self.config.get("streaming_preview"):
            self.overlay.show()
            self.streaming_thread = threading.Thread(target=self._streaming_loop, daemon=True)
            self.streaming_thread.start()

        max_seconds = self.config.get("max_record_seconds")
        try:
            max_seconds = int(max_seconds)
        except Exception:
            max_seconds = 0

        if max_seconds > 0:
            if self.auto_stop_timer:
                self.auto_stop_timer.cancel()
            self.auto_stop_timer = threading.Timer(max_seconds, lambda: self.queue.put("auto_stop_recording"))
            self.auto_stop_timer.daemon = True
            self.auto_stop_timer.start()
            log(f"Auto-stop armed at {max_seconds}s.")

    def _streaming_loop(self):
        log("Streaming loop started.")
        last_processed_idx = 0
        pause_between_runs = 1.8 # Seconds
        
        while self.is_recording:
            time.sleep(pause_between_runs)
            if not self.is_recording: break
            
            # Avoid processing too frequently if model is slow
            current_count = len(self.recorder.frames)
            if current_count <= last_processed_idx + 15: # approx 1s of audio min
                continue
            
            audio_path = self.recorder.get_current_audio_path()
            if audio_path:
                text = self.transcriber.transcribe(audio_path)
                try:
                    os.remove(audio_path)
                except: pass
                
                if text and self.is_recording:
                    self.last_partial_text = text
                    self.overlay.update_text(text)
                    log(f"Partial: {text[:30]}...")
            
            last_processed_idx = current_count

    def stop_recording_action(self):
        log("Action: Stop Recording")
        self.is_recording = False
        self.update_tray_icon(recording=False)

        if self.auto_stop_timer:
            self.auto_stop_timer.cancel()
            self.auto_stop_timer = None

        self.overlay.hide()

        try:
            import winsound
            winsound.Beep(400, 200)
        except: pass

        audio_path = self.recorder.stop()
        
        if audio_path:
            log(f"Audio captured: {audio_path}")
            threading.Thread(target=self.process_audio, args=(audio_path,), daemon=True).start()

    def update_tray_icon(self, recording=False, loading=False):
        if not self.tray_icon: return
        try:
            if loading:
                self.tray_icon.icon = self.icon_gray
                self.tray_icon.title = "CyberScribe - Chargement du modèle..."
            elif recording:
                self.tray_icon.icon = self.icon_red
                self.tray_icon.title = "CyberScribe - Enregistrement..."
            else:
                self.tray_icon.icon = self.icon_gray
                self.tray_icon.title = "CyberScribe - Prêt"
        except Exception as e:
            log_error(f"Error updating tray: {e}")

    def process_audio(self, audio_path):
        log("Transcribing...")
        text = self.transcriber.transcribe(audio_path)
        
        try:
            os.remove(audio_path)
        except: pass

        if text:
            log(f"Transcription result: [Redacted for security] ({len(text)} chars)")
            self.paste_text(text)
        else:
            log("No transcription result.")

    def paste_text(self, text):
        try:
            log("Attempting to paste text...")
            pyperclip.copy(text)
            time.sleep(0.3) 
            
            from pynput.keyboard import Controller, Key
            keyboard_controller = Controller()
            
            with keyboard_controller.pressed(Key.ctrl):
                keyboard_controller.press('v')
                keyboard_controller.release('v')
                
            log("Paste command sent.")
        except Exception as e:
            log_error(f"Error pasting text: {e}")
            try:
                log("Retrying with pyautogui...")
                pyautogui.hotkey('ctrl', 'v')
            except Exception as e2:
                log_error(f"Fallback paste failed: {e2}")

    # --- GUI & MAIN LOOP ---

    def request_settings(self, icon, item):
        self.queue.put("settings")

    def request_quit(self, icon, item):
        self.queue.put("quit")

    def open_settings_window(self):
        try:
            root = tk.Tk()
            root.title("CyberScribe Config")
            root.geometry("460x860")
            
            # Colors
            C_BG = '#0f172a'       # Dark Slate (Main BG)
            C_FG = '#e2e8f0'       # Light Silver (Text)
            C_ACCENT = '#06b6d4'   # Cyan (Headers/Buttons)
            C_ACCENT_HOVER = '#0891b2'
            C_INPUT_BG = '#1e293b' # Darker Slate (Inputs)
            C_INPUT_FG = '#38bdf8' # Sky Blue (Input Text)
            C_WARN = '#f43f5e'     # Rose (Test Button)
            
            root.configure(bg=C_ACCENT) 
            
            root.update_idletasks()
            width = 460
            height = 820
            x = (root.winfo_screenwidth() // 2) - (width // 2)
            y = (root.winfo_screenheight() // 2) - (height // 2)
            root.geometry(f'{width}x{height}+{x}+{y}')
            
            root.lift()
            root.attributes('-topmost',True)
            root.after_idle(root.attributes,'-topmost',False)

            main_frame = tk.Frame(root, bg=C_BG)
            main_frame.pack(fill='both', expand=True, padx=2, pady=2)

            style = ttk.Style()
            style.theme_use('clam')
            style.configure('TCombobox', fieldbackground=C_INPUT_BG, background=C_INPUT_BG, foreground=C_INPUT_FG, arrowcolor=C_ACCENT)
            
            def create_label(text, parent=main_frame):
                return tk.Label(parent, text=text, bg=C_BG, fg=C_ACCENT, font=("Segoe UI", 10, "bold"))

            def create_help_text(text, parent=main_frame):
                return tk.Label(parent, text=text, bg=C_BG, fg='#94a3b8', font=("Consolas", 8), justify='left', wraplength=400)

            def create_entry(var, parent=main_frame):
                e = tk.Entry(parent, textvariable=var, bg=C_INPUT_BG, fg=C_INPUT_FG, insertbackground=C_ACCENT, font=("Consolas", 11), relief='flat', bd=5)
                return e

            tk.Label(main_frame, text="/// SYSTEM CONFIGURATION", bg=C_BG, fg=C_ACCENT, font=("Consolas", 12, "bold")).pack(pady=(20, 10))
            tk.Frame(main_frame, bg=C_ACCENT, height=2).pack(fill='x', padx=20, pady=(0, 20))

            create_label(">> ACTIVATION KEY").pack(pady=(10, 2))
            create_help_text("Key binding for recording sequence (e.g., F8)").pack(pady=(0, 5))
            hk_var = tk.StringVar(value=self.config.get("hotkey"))
            create_entry(hk_var).pack(pady=0, ipadx=5, ipady=3)

            create_label(">> LANGUAGE MODULE").pack(pady=(15, 2))
            create_help_text("Target language for vocal processing.").pack(pady=(0, 5))
            lang_var = tk.StringVar(value=self.config.get("language") or "auto")
            LANGUAGES = ["auto", "en", "fr", "de", "es", "it", "ja", "zh", "nl", "uk", "pt", "ru"]
            lang_cb = ttk.Combobox(main_frame, textvariable=lang_var, values=LANGUAGES, font=("Consolas", 10))
            lang_cb.pack(pady=0)

            create_label(">> NEURAL MODEL").pack(pady=(15, 2))
            create_help_text("Model size: Tiny (Fast) <-> Large (Precise)").pack(pady=(0, 5))
            model_var = tk.StringVar(value=self.config.get("model_size"))
            model_cb = ttk.Combobox(main_frame, textvariable=model_var, values=["tiny", "base", "small", "medium", "large-v3"], font=("Consolas", 10))
            model_cb.pack(pady=0)

            create_label(">> PROCESSING UNIT").pack(pady=(15, 2))
            create_help_text("Compute device: CPU (Universal) / CUDA (GPU)").pack(pady=(0, 5))
            device_var = tk.StringVar(value=self.config.get("device"))
            device_cb = ttk.Combobox(main_frame, textvariable=device_var, values=["auto", "cpu", "cuda"], font=("Consolas", 10))
            device_cb.pack(pady=0)

            create_label(">> TRANSCRIPTION PROFILE").pack(pady=(15, 2))
            create_help_text("fast = low latency, balanced = compromise, accurate = quality").pack(pady=(0, 5))
            profile_var = tk.StringVar(value=self.config.get("transcription_profile") or "fast")
            profile_cb = ttk.Combobox(main_frame, textvariable=profile_var, values=["fast", "balanced", "accurate"], font=("Consolas", 10))
            profile_cb.pack(pady=0)

            create_label(">> MAX RECORD DURATION (SECONDS)").pack(pady=(15, 2))
            create_help_text("Auto-stop safety. 0 disables limit. Recommended: 15-30s").pack(pady=(0, 5))
            max_record_var = tk.StringVar(value=str(self.config.get("max_record_seconds") or 25))
            create_entry(max_record_var).pack(pady=0, ipadx=5, ipady=3)

            streaming_var = tk.BooleanVar(value=bool(self.config.get("streaming_preview")))
            tk.Checkbutton(main_frame, text="LIVE TRANSLATION PREVIEW (STREAMING)", variable=streaming_var, bg=C_BG, fg=C_ACCENT, selectcolor=C_BG, activebackground=C_BG, activeforeground=C_ACCENT, font=("Segoe UI", 9, "bold")).pack(pady=10)

            create_label(">> MODEL STORAGE").pack(pady=(15, 2))
            path_var = tk.StringVar(value=MODELS_DIR)
            path_entry = tk.Entry(main_frame, textvariable=path_var, bg=C_INPUT_BG, fg='#94a3b8', font=("Consolas", 9), relief='flat', bd=5, state='readonly', readonlybackground=C_INPUT_BG)
            path_entry.pack(pady=0, fill='x', padx=30)

            def test_rec():
                self.queue.put("toggle_recording")
            tk.Button(main_frame, text="[ INITIATE SELF-TEST ]", command=test_rec, bg=C_WARN, fg="white", font=("Consolas", 9, "bold"), relief='flat').pack(pady=(30, 5), ipadx=10)

            def save():
                self.config.set("hotkey", hk_var.get())
                self.config.set("language", lang_var.get())
                self.config.set("model_size", model_var.get())
                self.config.set("device", device_var.get())
                self.config.set("transcription_profile", profile_var.get() or "fast")
                try:
                    self.config.set("max_record_seconds", int(max_record_var.get()))
                except: pass
                self.config.set("streaming_preview", streaming_var.get())
                self.setup_hotkey()
                messagebox.showinfo("CyberScribe", "SYSTEM UPDATED.", parent=root)
                root.destroy()

            tk.Button(main_frame, text=">> SAVE CONFIGURATION <<", command=save, bg=C_ACCENT, fg="white", font=("Consolas", 11, "bold"), relief='flat').pack(pady=10, ipadx=20, ipady=5)
            root.mainloop()
        except Exception as e:
            log_error(f"GUI Error: {e}")

    def show_splash(self):
        try:
            splash = tk.Tk()
            splash.overrideredirect(True)
            splash.attributes('-topmost', True)
            w, h = 400, 100
            ws, hs = splash.winfo_screenwidth(), splash.winfo_screenheight()
            x, y = (ws/2) - (w/2), (hs/2) - (h/2)
            splash.geometry(f'{w}x{h}+{int(x)}+{int(y)}')
            frame = tk.Frame(splash, bg='#1f2937', relief='raised', bd=2)
            frame.pack(fill='both', expand=True)
            tk.Label(frame, text="CyberScribe", font=("Segoe UI", 16, "bold"), bg='#1f2937', fg='white').pack(pady=(20,5))
            tk.Label(frame, text="Prêt à l'écoute. Appuyez sur votre raccourci.", font=("Segoe UI", 10), bg='#1f2937', fg='#d1d5db').pack(pady=(0,20))
            splash.after(3000, splash.destroy)
            splash.mainloop()
        except Exception as e:
            log_error(f"Splash error: {e}")

    def run_tray(self):
        menu = pystray.Menu(
            pystray.MenuItem("Configuration", self.request_settings),
            pystray.MenuItem("Quitter", self.request_quit)
        )
        self.tray_icon = pystray.Icon("CyberScribe", self.icon_gray, "CyberScribe - Prêt", menu)
        self.tray_icon.run()

    def run(self):
        log("=== Application Started ===")
        self.show_splash()
        tray_thread = threading.Thread(target=self.run_tray, daemon=True)
        tray_thread.start()
        self.update_tray_icon(loading=True)
        while True:
            try:
                try:
                    msg = self.queue.get(timeout=0.5)
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
                elif msg == "quit":
                    self.stop_app()
                    break
            except KeyboardInterrupt:
                break

    def stop_app(self):
        log("Stopping...")
        try:
            self.recorder.terminate()
            if self.hotkey_listener:
                self.hotkey_listener.stop()
            if self.tray_icon:
                self.tray_icon.stop()
        except: pass
        os._exit(0)

if __name__ == "__main__":
    app = CyberScribeApp()
    app.run()
