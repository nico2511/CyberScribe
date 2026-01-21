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
import wave
import tempfile
import base64
import queue
import logging
from io import BytesIO
import tkinter as tk
from tkinter import ttk, messagebox

# Configure Logging
LOG_FILE = "debug_CyberScribe.log"
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

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
# CONFIGURATION
# ==================================================================================

CONFIG_FILE = "config.json"
DEFAULT_CONFIG = {
    "hotkey": "F8",
    "language": "fr",
    "model_size": "base",
    "device": "cpu",
    "compute_type": "int8"
}

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
                data = self.stream.read(self.chunk)
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
        threading.Thread(target=self._load_model, daemon=True).start()

    def _load_model(self):
        self.loading = True
        try:
            model_size = self.config.get("model_size")
            device = self.config.get("device")
            compute_type = self.config.get("compute_type")
            log(f"Loading Whisper Model ({model_size})...")
            self.model = WhisperModel(model_size, device=device, compute_type=compute_type)
            log("Model loaded.")
        except Exception as e:
            log_error(f"Error loading model: {e}")
            self.model = None
        self.loading = False

    def transcribe(self, audio_path):
        if not self.model:
            if self.loading:
                return "Erreur: Modèle en cours de chargement..."
            else:
                self._load_model()
                if not self.model: 
                    return "Erreur: Modèle non chargé."
        
        try:
            lang = self.config.get("language")
            if lang == "auto":
                lang = None
            
            segments, info = self.model.transcribe(audio_path, beam_size=5, language=lang)
            text_result = "".join([segment.text for segment in segments]).strip()
            return text_result
        except Exception as e:
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
        # Basic mapping for function keys and simple letters.
        # This is a simplification; pynput key strings are case-insensitive mostly.
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
        # Use queue to handle logic in main thread or handle specifically
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

    def stop_recording_action(self):
        log("Action: Stop Recording")
        self.is_recording = False
        self.update_tray_icon(recording=False)

        try:
            import winsound
            winsound.Beep(400, 200)
        except: pass

        audio_path = self.recorder.stop()
        
        if audio_path:
            log(f"Audio captured: {audio_path}")
            threading.Thread(target=self.process_audio, args=(audio_path,), daemon=True).start()

    def update_tray_icon(self, recording):
        if not self.tray_icon: return
        try:
            if recording:
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
            log(f"Transcription result: {text}")
            self.paste_text(text)
        else:
            log("No transcription result.")

    def paste_text(self, text):
        try:
            pyperclip.copy(text)
            time.sleep(0.1) 
            pyautogui.hotkey('ctrl', 'v')
        except Exception as e:
            log_error(f"Error pasting text: {e}")

    # --- GUI & MAIN LOOP ---

    def request_settings(self, icon, item):
        self.queue.put("settings")

    def request_quit(self, icon, item):
        self.queue.put("quit")

    def open_settings_window(self):
        try:
            root = tk.Tk()
            root.title("CyberScribe Config")
            root.geometry("460x680")
            
            # Colors
            C_BG = '#0f172a'       # Dark Slate (Main BG)
            C_FG = '#e2e8f0'       # Light Silver (Text)
            C_ACCENT = '#06b6d4'   # Cyan (Headers/Buttons)
            C_ACCENT_HOVER = '#0891b2'
            C_INPUT_BG = '#1e293b' # Darker Slate (Inputs)
            C_INPUT_FG = '#38bdf8' # Sky Blue (Input Text)
            C_WARN = '#f43f5e'     # Rose (Test Button)
            
            root.configure(bg=C_ACCENT) # Border color via padding
            
            # Center window
            root.update_idletasks()
            width = 460
            height = 680
            x = (root.winfo_screenwidth() // 2) - (width // 2)
            y = (root.winfo_screenheight() // 2) - (height // 2)
            root.geometry(f'{width}x{height}+{x}+{y}')
            
            root.lift()
            root.attributes('-topmost',True)
            root.after_idle(root.attributes,'-topmost',False)

            # Main Container (slightly smaller than root to show border)
            main_frame = tk.Frame(root, bg=C_BG)
            main_frame.pack(fill='both', expand=True, padx=2, pady=2)

            style = ttk.Style()
            style.theme_use('clam')
            style.configure('TCombobox', 
                            fieldbackground=C_INPUT_BG, 
                            background=C_INPUT_BG, 
                            foreground=C_INPUT_FG, 
                            arrowcolor=C_ACCENT,
                            bordercolor=C_ACCENT,
                            lightcolor=C_INPUT_BG,
                            darkcolor=C_INPUT_BG)
            
            # --- Helpers ---
            def create_label(text, parent=main_frame):
                return tk.Label(parent, text=text, bg=C_BG, fg=C_ACCENT, font=("Segoe UI", 10, "bold"))

            def create_help_text(text, parent=main_frame):
                return tk.Label(parent, text=text, bg=C_BG, fg='#94a3b8', font=("Consolas", 8), justify='left', wraplength=400)

            def create_entry(var, parent=main_frame):
                e = tk.Entry(parent, textvariable=var, bg=C_INPUT_BG, fg=C_INPUT_FG, 
                             insertbackground=C_ACCENT, font=("Consolas", 11), 
                             relief='flat', bd=5)
                return e

            # Top Title
            tk.Label(main_frame, text="/// SYSTEM CONFIGURATION", bg=C_BG, fg=C_ACCENT, font=("Consolas", 12, "bold")).pack(pady=(20, 10))
            tk.Frame(main_frame, bg=C_ACCENT, height=2).pack(fill='x', padx=20, pady=(0, 20))

            # --- Form ---

            # Hotkey
            create_label(">> ACTIVATION KEY").pack(pady=(10, 2))
            create_help_text("Key binding for recording sequence (e.g., F8)").pack(pady=(0, 5))
            hk_var = tk.StringVar(value=self.config.get("hotkey"))
            create_entry(hk_var).pack(pady=0, ipadx=5, ipady=3)

            # Language
            create_label(">> LANGUAGE MODULE").pack(pady=(15, 2))
            create_help_text("Target language for vocal processing.").pack(pady=(0, 5))
            lang_var = tk.StringVar(value=self.config.get("language") or "auto")
            
            LANGUAGES = [
                "auto", "en", "fr", "de", "es", "it", "ja", "zh", "nl", "uk", "pt", "ru", 
                "ko", "pl", "tr", "ar", "cs", "el", "fi", "he", "hi", "hu", "id", "ms", 
                "no", "ro", "sv", "th", "vi"
            ]
            lang_cb = ttk.Combobox(main_frame, textvariable=lang_var, values=LANGUAGES, font=("Consolas", 10))
            lang_cb.pack(pady=0)

            # Model
            create_label(">> NEURAL MODEL").pack(pady=(15, 2))
            create_help_text("Model size: Tiny (Fast) <-> Large (Precise)").pack(pady=(0, 5))
            
            model_var = tk.StringVar(value=self.config.get("model_size"))
            model_cb = ttk.Combobox(main_frame, textvariable=model_var, values=["tiny", "base", "small", "medium", "large-v3"], font=("Consolas", 10))
            model_cb.pack(pady=0)

            # Device
            create_label(">> PROCESSING UNIT").pack(pady=(15, 2))
            create_help_text("Compute device: CPU (Universal) / CUDA (GPU)").pack(pady=(0, 5))
            
            device_var = tk.StringVar(value=self.config.get("device"))
            device_cb = ttk.Combobox(main_frame, textvariable=device_var, values=["cpu", "cuda"], font=("Consolas", 10))
            device_cb.pack(pady=0)

            # Buttons
            def test_rec():
                self.queue.put("toggle_recording")

            tk.Button(main_frame, text="[ INITIATE SELF-TEST ]", command=test_rec, 
                      bg=C_WARN, fg="white", font=("Consolas", 9, "bold"), 
                      relief='flat', activebackground='#e11d48', activeforeground='white', cursor="hand2").pack(pady=(30, 5), ipadx=10)

            def save():
                new_hk = hk_var.get()
                new_lang = lang_var.get()
                if new_lang == "auto": new_lang = None
                new_model = model_var.get()
                new_device = device_var.get()

                self.config.set("hotkey", new_hk)
                self.config.set("language", new_lang)
                self.config.set("model_size", new_model)
                self.config.set("device", new_device)
                
                self.setup_hotkey()
                messagebox.showinfo("CyberScribe", "SYSTEM UPDATED SUCCESSFULLY.", parent=root)
                root.destroy()

            tk.Button(main_frame, text=">> SAVE CONFIGURATION <<", command=save, 
                      bg=C_ACCENT, fg="white", font=("Consolas", 11, "bold"), 
                      relief='flat', activebackground=C_ACCENT_HOVER, activeforeground='white', cursor="hand2").pack(pady=10, ipadx=20, ipady=5)
            
            root.mainloop()
        except Exception as e:
            log_error(f"GUI Error: {e}")

    def show_splash(self):
        try:
            splash = tk.Tk()
            splash.overrideredirect(True)  # Frameless
            splash.attributes('-topmost', True)
            
            # Position center
            w, h = 400, 100
            ws, hs = splash.winfo_screenwidth(), splash.winfo_screenheight()
            x, y = (ws/2) - (w/2), (hs/2) - (h/2)
            splash.geometry(f'{w}x{h}+{int(x)}+{int(y)}')
            
            frame = tk.Frame(splash, bg='#1f2937', relief='raised', bd=2)
            frame.pack(fill='both', expand=True)
            
            tk.Label(frame, text="CyberScribe", font=("Segoe UI", 16, "bold"), bg='#1f2937', fg='white').pack(pady=(20,5))
            tk.Label(frame, text="Prêt à l'écoute. Appuyez sur votre raccourci.", font=("Segoe UI", 10), bg='#1f2937', fg='#d1d5db').pack(pady=(0,20))
            
            # Auto close after 3 seconds
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
        
        while True:
            try:
                msg = self.queue.get(timeout=0.5)
                
                if msg == "settings":
                    self.open_settings_window()
                elif msg == "toggle_recording":
                    self.toggle_recording()
                elif msg == "quit":
                    self.stop_app()
                    break
            except queue.Empty:
                if not tray_thread.is_alive():
                    break
                continue
            except KeyboardInterrupt:
                break

    def stop_app(self):
        log("Stopping...")
        self.recorder.terminate()
        if self.hotkey_listener:
            self.hotkey_listener.stop()
        if self.tray_icon:
            self.tray_icon.stop()
        sys.exit(0)

if __name__ == "__main__":
    app = CyberScribeApp()
    
    app.run()
