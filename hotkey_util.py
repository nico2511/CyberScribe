"""Hotkey normalization and labels (no CyberScribe import)."""

from __future__ import annotations

from cyber_config import DEFAULT_CONFIG

HOTKEY_MODIFIERS = {
    "ctrl": "<ctrl>",
    "control": "<ctrl>",
    "alt": "<alt>",
    "shift": "<shift>",
    "cmd": "<cmd>",
    "win": "<cmd>",
}

MOUSE_HOTKEYS = {
    "mouse_x1": "x1",
    "mouse_x2": "x2",
    "mouse_middle": "middle",
}
MOUSE_HOTKEY_ALIASES = {
    "mouse_x1": "mouse_x1",
    "mouse:x1": "mouse_x1",
    "x1": "mouse_x1",
    "button4": "mouse_x1",
    "souris_x1": "mouse_x1",
    "mouse_x2": "mouse_x2",
    "mouse:x2": "mouse_x2",
    "x2": "mouse_x2",
    "button5": "mouse_x2",
    "souris_x2": "mouse_x2",
    "mouse_middle": "mouse_middle",
    "mouse:middle": "mouse_middle",
    "middle": "mouse_middle",
    "souris_molette": "mouse_middle",
    "mouse_mid": "mouse_middle",
}
MOUSE_HOTKEY_LABELS = {
    "mouse_x1": "Souris X1 (latéral)",
    "mouse_x2": "Souris X2 (latéral)",
    "mouse_middle": "Souris molette (clic)",
}


def normalize_hotkey(raw):
    raw = str(raw or "").strip()
    if not raw:
        return DEFAULT_CONFIG["hotkey"]
    alias = MOUSE_HOTKEY_ALIASES.get(raw.lower().replace(" ", ""))
    if alias:
        return alias
    parts = [p.strip() for p in raw.replace(" ", "").split("+") if p.strip()]
    if not parts:
        return DEFAULT_CONFIG["hotkey"]
    pretty = []
    for part in parts:
        low = part.strip("<>").lower()
        if low in ("control", "ctrl"):
            pretty.append("ctrl")
        elif low in ("win", "cmd"):
            pretty.append("cmd")
        elif low in HOTKEY_MODIFIERS:
            pretty.append(low)
        elif low.startswith("f") and low[1:].isdigit():
            pretty.append(low.upper())
        else:
            pretty.append(low)
    return "+".join(pretty) if pretty else DEFAULT_CONFIG["hotkey"]


def is_mouse_hotkey(raw):
    return normalize_hotkey(raw) in MOUSE_HOTKEYS


def display_hotkey(raw):
    canon = normalize_hotkey(raw)
    if canon in MOUSE_HOTKEY_LABELS:
        return MOUSE_HOTKEY_LABELS[canon]
    return canon


def format_hotkey(raw):
    canon = normalize_hotkey(raw)
    if canon in MOUSE_HOTKEYS:
        return canon
    parts = [p.strip().lower() for p in canon.replace(" ", "").split("+") if p.strip()]
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