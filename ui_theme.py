"""Shared Tk styling for CyberScribe windows (no CyberScribe import)."""

from __future__ import annotations

C_BG = "#0f172a"
C_ACCENT = "#06b6d4"
C_INPUT_BG = "#1e293b"
C_INPUT_FG = "#06b6d4"
C_MUTED = "#94a3b8"
C_TEXT = "#e2e8f0"
C_WARN = "#f43f5e"
C_CARD_BORDER = "#334155"
C_CARD_SELECTED = "#06b6d4"
C_CARD_SELECTED_BG = "#164e63"
C_FOOTER_BTN_FG = "#0f172a"

CONFIG_WINDOW_WIDTH = 690
CONFIG_WINDOW_HEIGHT = 700
FIRST_RUN_WIDTH = 690
FIRST_RUN_HEIGHT = 640

CONTENT_PADX = 24

FONT_UI = ("Segoe UI", 10)
FONT_UI_BOLD = ("Segoe UI", 10, "bold")
FONT_UI_SEMI = ("Segoe UI Semibold", 10)
FONT_UI_SECTION = ("Segoe UI Semibold", 10)
FONT_UI_SMALL = ("Segoe UI", 9)
FONT_HEADER_MONO = ("Consolas", 13)
FONT_MONO = ("Consolas", 10)
FONT_MONO_SMALL = ("Consolas", 9)
FONT_TITLE = ("Segoe UI", 14, "bold")

LANGUAGE_LABELS = {
    "auto": "Détection automatique",
    "en": "English (en)",
    "fr": "Français (fr)",
    "de": "Deutsch (de)",
    "es": "Español (es)",
    "it": "Italiano (it)",
    "ja": "日本語 (ja)",
    "zh": "中文 (zh)",
    "nl": "Nederlands (nl)",
    "uk": "Українська (uk)",
    "pt": "Português (pt)",
    "ru": "Русский (ru)",
}

PROFILE_CARD_COPY = {
    "fast": ("Rapide", "réponse la plus vive\nidéal phrases courtes"),
    "balanced": ("Équilibré", "bon compromis\npour la plupart"),
    "accurate": ("Précis", "plus lent, moins\nd'erreurs sur les noms"),
}

MODEL_CARD_COPY = {
    "tiny": ("Ultra-léger", "tiny · pour un vieux PC", "≈ 75 Mo"),
    "base": ("Recommandé", "base · bon équilibre, réglage actuel", "≈ 145 Mo"),
    "small": ("Plus juste", "small · un peu plus lent", "≈ 480 Mo"),
}