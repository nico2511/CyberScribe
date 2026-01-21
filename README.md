# 🤖 CyberScribe

**CyberScribe** is a local, offline voice transcription tool powered by `faster-whisper`. It features a robot-themed UI, system tray integration, and global hotkeys for instant recording.

![Configuration Window](screenshots/sc.png)

## Features

- 🎙️ **Offline Transcription**: Powered by Faster-Whisper.
- 🤖 **Robot Theme**: Custom icons and splash screen.
- ⌨️ **Global Hotkey**: Toggle recording from anywhere (default F8).
- 📋 **Auto-Paste**: Automatically pastes transcribed text.
- ⚙️ **Configurable**: Change models, hotkeys, and language via settings.

## Installation / Compilation

To compile the application into a standalone `.exe`:

1.  **Install Dependencies**:
    ```bash
    pip install faster-whisper pyaudio pystray Pillow pyperclip pyautogui pynput
    ```
    *Note: If `pyaudio` fails, try using `pipwin install pyaudio`.*

2.  **Build with PyInstaller**:
    ```bash
    pyinstaller --noconsole --onefile --noconfirm --hidden-import=pyaudio --hidden-import=pynput.keyboard._win32 --hidden-import=pynput.mouse._win32 --icon "app.ico" --name "CyberScribe" CyberScribe.py
    ```

## Usage

1.  Run the executable.
2.  Wait for the Splash Screen.
3.  Press **F8** (or your configured hotkey) to start recording.
4.  Press **F8** again to stop.
5.  The text will be transcribed and pasted automatically.

## Model Comparison

Choose the right model for your needs:

| Model | Speed | Accuracy | Recommended Use |
|-------|-------|----------|-----------------|
| **tiny** | ⚡⚡⚡ Very Fast | ⭐⭐ Basic | Quick tests |
| **base** | ⚡⚡ Fast | ⭐⭐⭐ Good | **Daily use** ✅ (Default) |
| **small** | ⚡ Medium | ⭐⭐⭐⭐ Very Good | Quality/Speed balance |
| **medium** | 🐌 Slow | ⭐⭐⭐⭐⭐ Excellent | Critical transcription |
| **large-v3** | 🐌🐌 Very Slow | ⭐⭐⭐⭐⭐ Maximum | Professional only |

> **Note**: The **base** model offers the best balance for everyday use. Use **medium** or **large-v3** only when maximum accuracy is required and you can accept longer processing times.
