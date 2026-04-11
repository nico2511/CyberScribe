# 🤖 CyberScribe

**CyberScribe** is a local, offline voice transcription tool powered by `faster-whisper`. It features a robot-themed UI, system tray integration, and global hotkeys for instant recording with **real-time streaming preview**.

![Configuration Window](screenshots/sc.png)

## 🚀 New Features

- ⚡ **Partial Streaming**: Live transcription preview in a floating overlay window during recording.
- 📉 **Anti-Latency Engine**: Configurable performance profiles (Fast, Balanced, Accurate) to match your hardware.
- 📟 **Smart Device Detection**: Automatic CUDA (NVIDIA GPU) or CPU selection for maximum efficiency.
- ⏱️ **Auto-Stop Safety**: Configurable maximum recording duration to prevent runaway dictation.
- 🎙️ **Audio Robustness**: Improved audio handling with overflow protection.

## Core Features

- 🎙️ **Offline Transcription**: Powered by Faster-Whisper.
- ⌨️ **Global Hotkey**: Toggle recording from anywhere (default F8).
- 🔊 **Audio Feedback**: Audible cues (beeps) when starting and stopping records.
- 📋 **Auto-Paste**: Automatically pastes transcribed text into your active window.
- 🧪 **System Self-Test**: Integrated diagnostic tool to verify your setup.

## Installation / Compilation

### Local Development
1. **Install Dependencies**:
   ```bash
   pip install faster-whisper pyaudio pystray Pillow pyperclip pyautogui pynput
   ```

2. **Run Script**:
   ```bash
   python CyberScribe.py
   ```

### Build your own EXE
```bash
pyinstaller --noconsole --onefile --noconfirm --hidden-import=pyaudio --hidden-import=pynput.keyboard._win32 --hidden-import=pynput.mouse._win32 --add-data "venv\Lib\site-packages\faster_whisper\assets\silero_vad_v6.onnx;faster_whisper/assets" --icon "app.ico" --name "CyberScribe" CyberScribe.py
```
*(Note: adjust the path to silero_vad_v6.onnx according to your python installation location)*

## Ci/CD (Automated Builds)
This repository is configured with **GitHub Actions**. Every time you push a tag or a new release, an executable is automatically built and attached to the release page.


## Usage

1. Run the executable.
2. Wait for the Splash Screen.
3. Press **F8** (or your configured hotkey) to start recording. You will hear a **high beep**.
4. A **Live Preview** window will show your text as you speak.
5. Press **F8** again to stop. The final text will be pasted automatically.

## Support

If you like CyberScribe, consider supporting the project!

**Bitcoin (BTC)**: `bc1pt20cczcmvukrny4pru3x2nc522tk2sectlu22d42q2ltyau7t66suh6kqx`
