"""Status overlay bar and testable UI logic (no dictated text in strings here)."""

from __future__ import annotations

import math
import struct
import threading
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, List, Optional, Sequence, Tuple

if TYPE_CHECKING:
    import tkinter as tk

# Visual constants (match existing CyberScribe palette)
BG_DARK = "#0b1120"
ACCENT_CYAN = "#00f2ff"
CYAN_DIM = "#0e7490"
CYAN_BRIGHT = "#00f2ff"
OVERLAY_W = 400
OVERLAY_H = 38
BAR_COUNT = 48
VU_REFRESH_MS = 40  # ~25 Hz
ENDING_SOON_SECONDS = 3
PASTED_HIDE_MS = 1500

PROFILE_LABELS = {
    "fast": "Rapide",
    "balanced": "Équilibré",
    "accurate": "Précis",
}


class OverlayState(str, Enum):
    HIDDEN = "hidden"
    LISTENING = "listening"
    ENDING_SOON = "ending_soon"
    TRANSCRIBING = "transcribing"
    PASTED = "pasted"
    ERROR = "error"
    CANCELLED = "cancelled"


@dataclass(frozen=True)
class OverlayPalette:
    border: str
    pill_bg: str
    pill_fg: str
    detail_fg: str


STATE_PALETTE = {
    OverlayState.LISTENING: OverlayPalette(ACCENT_CYAN, "#db2777", "#ffffff", ACCENT_CYAN),
    OverlayState.ENDING_SOON: OverlayPalette("#f59e0b", "#f59e0b", "#111827", "#fbbf24"),
    OverlayState.TRANSCRIBING: OverlayPalette(ACCENT_CYAN, ACCENT_CYAN, "#0b1120", "#94a3b8"),
    OverlayState.PASTED: OverlayPalette("#22c55e", "#22c55e", "#0b1120", "#bbf7d0"),
    OverlayState.ERROR: OverlayPalette("#f43f5e", "#be123c", "#ffffff", "#fecdd3"),
    OverlayState.CANCELLED: OverlayPalette("#6b7280", "#4b5563", "#e5e7eb", "#9ca3af"),
}


def format_record_timer(elapsed_s: float, max_s: int) -> str:
    """Chrono label, e.g. ``0:07 / 0:25`` (Consolas in UI)."""
    elapsed_s = max(0.0, float(elapsed_s))
    max_s = max(0, int(max_s))

    def _part(seconds: float) -> str:
        whole = int(seconds)
        return f"{whole // 60}:{whole % 60:02d}"

    if max_s <= 0:
        return _part(elapsed_s)
    return f"{_part(elapsed_s)} / {_part(max_s)}"


def format_pasted_detail(char_count: int, dictation_s: float) -> str:
    """Success detail without transcribed content."""
    char_count = max(0, int(char_count))
    dictation_s = max(0.0, float(dictation_s))
    if dictation_s < 10:
        dur = f"{dictation_s:.1f}".replace(".", ",")
    else:
        dur = str(int(round(dictation_s)))
    return f"{char_count} caractères · {dur} s"


def ending_soon_remaining(elapsed_s: float, max_s: int, threshold: int = ENDING_SOON_SECONDS) -> Optional[int]:
    """Seconds until auto-stop, or None if not in the ending-soon window."""
    if max_s <= 0:
        return None
    remaining = max_s - elapsed_s
    if remaining <= 0 or remaining > threshold:
        return None
    return max(1, int(math.ceil(remaining)))


def overlay_state_for_recording(elapsed_s: float, max_s: int) -> OverlayState:
    if ending_soon_remaining(elapsed_s, max_s) is not None:
        return OverlayState.ENDING_SOON
    return OverlayState.LISTENING


def pcm16_chunk_rms(chunk: bytes) -> float:
    """RMS level in 0..1 from mono PCM16 bytes."""
    if not chunk or len(chunk) < 2:
        return 0.0
    n = len(chunk) // 2
    if n <= 0:
        return 0.0
    samples = struct.unpack(f"<{n}h", chunk[: n * 2])
    if not samples:
        return 0.0
    sum_sq = sum(s * s for s in samples)
    rms = math.sqrt(sum_sq / n)
    return min(1.0, rms / 32768.0)


def vu_meter_bar_levels(
    history: Sequence[float],
    *,
    pre_buffer_bars: int,
) -> Tuple[List[float], int]:
    """Return bar heights and the index of the F8 separator (or -1)."""
    pre_buffer_bars = max(0, int(pre_buffer_bars))
    if pre_buffer_bars <= 0:
        return list(history)[-BAR_COUNT:], -1
    split = min(pre_buffer_bars, BAR_COUNT - 1)
    bars = list(history)[-BAR_COUNT:]
    while len(bars) < BAR_COUNT:
        bars.insert(0, 0.0)
    return bars, split


def pre_buffer_bar_count(pre_buffer_ms: int, refresh_hz: float = 25.0) -> int:
    if pre_buffer_ms <= 0:
        return 0
    duration_s = pre_buffer_ms / 1000.0
    return max(1, int(round(duration_s * refresh_hz)))


def resolve_device_label(device_config: str, cuda_available: bool) -> str:
    pref = (device_config or "auto").lower()
    if pref == "cuda":
        return "CUDA"
    if pref == "cpu":
        return "CPU"
    return "CUDA" if cuda_available else "CPU"


def tray_status_line(
    state: str,
    model_size: str,
    device: str,
    profile: str,
) -> str:
    profile_short = profile if profile in ("fast", "balanced", "accurate") else "fast"
    return f"{state} · {model_size} · {device} · {profile_short}"


class StatusOverlay:
    """Bottom status bar overlay (~400×38). Updates must run on the Tk main thread."""

    def __init__(self, master):
        import tkinter as tk

        self._tk = tk
        self.master = master
        self.window = None
        self._outer = None
        self._pill = None
        self._detail = None
        self._timer = None
        self._canvas = None
        self._progress = None
        self._state = OverlayState.HIDDEN
        self._vu_history: List[float] = []
        self._pre_buffer_bars = 0
        self._hide_after_id: Optional[str] = None
        self._tick_after_id: Optional[str] = None
        self._level_provider = None
        self._timer_provider = None
        self._lock = threading.Lock()

    def set_level_provider(self, provider):
        """Callable returning current RMS 0..1 (may be invoked from worker threads)."""
        self._level_provider = provider

    def set_timer_provider(self, provider):
        """Callable returning (elapsed_s, max_s) for the chrono."""
        self._timer_provider = provider

    def _ensure_window(self):
        tk = self._tk
        if self.window:
            return
        self.window = tk.Toplevel(self.master)
        self.window.overrideredirect(True)
        self.window.attributes("-topmost", True)
        self.window.attributes("-alpha", 0.92)

        screen_w = self.window.winfo_screenwidth()
        screen_h = self.window.winfo_screenheight()
        x = (screen_w - OVERLAY_W) // 2
        y = screen_h - OVERLAY_H - 48
        self.window.geometry(f"{OVERLAY_W}x{OVERLAY_H}+{x}+{y}")

        self._outer = tk.Frame(self.window, bg=BG_DARK)
        self._outer.pack(fill="both", expand=True)

        self._pill = tk.Label(
            self._outer,
            text="",
            font=("Segoe UI Semibold", 10),
            width=18,
            anchor="w",
            padx=10,
        )
        self._pill.pack(side="left", fill="y")

        right = tk.Frame(self._outer, bg=BG_DARK)
        right.pack(side="left", fill="both", expand=True)

        self._canvas = tk.Canvas(right, height=22, bg=BG_DARK, highlightthickness=0)
        self._canvas.pack(fill="x", padx=(0, 8), pady=(4, 0))

        self._progress = tk.Canvas(right, height=3, bg=BG_DARK, highlightthickness=0)

        bottom = tk.Frame(right, bg=BG_DARK)
        bottom.pack(fill="x", padx=(0, 10), pady=(0, 4))
        self._detail = tk.Label(bottom, text="", font=("Segoe UI", 9), bg=BG_DARK, anchor="w")
        self._detail.pack(side="left", fill="x", expand=True)
        self._timer = tk.Label(bottom, text="", font=("Consolas", 9), bg=BG_DARK, anchor="e")
        self._timer.pack(side="right")

    def _cancel_timers(self):
        for attr in ("_hide_after_id", "_tick_after_id"):
            aid = getattr(self, attr)
            if aid and self.window:
                try:
                    self.window.after_cancel(aid)
                except Exception:
                    pass
            setattr(self, attr, None)

    def _apply_palette(self, state: OverlayState):
        pal = STATE_PALETTE.get(state)
        if not pal or not self.window:
            return
        self.window.config(bg=pal.border)
        if self._outer:
            self._outer.config(bg=BG_DARK)
        if self._pill:
            self._pill.config(bg=pal.pill_bg, fg=pal.pill_fg)
        if self._detail:
            self._detail.config(fg=pal.detail_fg, bg=BG_DARK)
        if self._timer:
            self._timer.config(fg=pal.detail_fg, bg=BG_DARK)

    def show_state(
        self,
        state: OverlayState,
        *,
        pill_text: str,
        detail_text: str = "",
        timer_text: str = "",
        pre_buffer_ms: int = 0,
        auto_hide_ms: Optional[int] = None,
    ):
        self._cancel_timers()
        self._state = state
        if state == OverlayState.HIDDEN:
            self.hide()
            return

        self._ensure_window()
        self._apply_palette(state)
        self._pre_buffer_bars = pre_buffer_bar_count(pre_buffer_ms)

        if self._pill:
            self._pill.config(text=pill_text)
        if self._detail:
            self._detail.config(text=detail_text)
        if self._timer:
            self._timer.config(text=timer_text)

        show_vu = state in (OverlayState.LISTENING, OverlayState.ENDING_SOON)
        if self._canvas:
            if show_vu:
                self._canvas.pack(fill="x", padx=(0, 8), pady=(4, 0))
            else:
                self._canvas.pack_forget()

        if self._progress:
            if state == OverlayState.ENDING_SOON:
                self._progress.pack(fill="x", padx=(0, 8))
            else:
                self._progress.pack_forget()

        if show_vu:
            self._start_vu_tick()
        else:
            self._stop_vu_tick()
            if self._canvas:
                self._canvas.delete("all")

        if auto_hide_ms and self.window:
            self._hide_after_id = self.window.after(auto_hide_ms, self.hide)

    def hide(self):
        self._cancel_timers()
        self._stop_vu_tick()
        self._state = OverlayState.HIDDEN
        self._vu_history.clear()
        if self.window:
            try:
                self.window.destroy()
            except Exception:
                pass
        self.window = None
        self._outer = None
        self._pill = None
        self._detail = None
        self._timer = None
        self._canvas = None
        self._progress = None

    def _stop_vu_tick(self):
        if self._tick_after_id and self.window:
            try:
                self.window.after_cancel(self._tick_after_id)
            except Exception:
                pass
        self._tick_after_id = None

    def _start_vu_tick(self):
        self._stop_vu_tick()
        if self.window:
            self._tick_after_id = self.window.after(VU_REFRESH_MS, self._vu_tick)

    def _vu_tick(self):
        if self._state not in (OverlayState.LISTENING, OverlayState.ENDING_SOON):
            return
        level = 0.0
        if self._level_provider:
            try:
                level = float(self._level_provider())
            except Exception:
                level = 0.0
        with self._lock:
            self._vu_history.append(level)
            if len(self._vu_history) > BAR_COUNT * 2:
                self._vu_history = self._vu_history[-BAR_COUNT * 2 :]

        elapsed_s = 0.0
        max_s = 0
        if self._timer_provider:
            try:
                elapsed_s, max_s = self._timer_provider()
            except Exception:
                pass

        remaining = ending_soon_remaining(elapsed_s, max_s)
        new_state = OverlayState.ENDING_SOON if remaining else OverlayState.LISTENING
        if new_state != self._state:
            self._state = new_state
            self._apply_palette(new_state)
            if new_state == OverlayState.ENDING_SOON and self._pill and remaining:
                self._pill.config(text=f"● Fin dans {remaining} s")
            elif self._pill:
                self._pill.config(text="● Écoute")
            if self._progress:
                if new_state == OverlayState.ENDING_SOON:
                    self._progress.pack(fill="x", padx=(0, 8))
                else:
                    self._progress.pack_forget()
            if self._timer_provider and self._timer:
                self._timer.config(text=format_record_timer(elapsed_s, max_s))

        self._draw_vu_meter()
        if self.window:
            self._tick_after_id = self.window.after(VU_REFRESH_MS, self._vu_tick)

    def _draw_vu_meter(self):
        if not self._canvas:
            return
        c = self._canvas
        c.delete("all")
        w = max(10, c.winfo_width())
        h = max(8, c.winfo_height())
        with self._lock:
            bars, split = vu_meter_bar_levels(self._vu_history, pre_buffer_bars=self._pre_buffer_bars)
        bar_w = max(2, w // BAR_COUNT)
        gap = 1
        pal = STATE_PALETTE.get(self._state, STATE_PALETTE[OverlayState.LISTENING])
        bright = pal.detail_fg if self._state == OverlayState.ENDING_SOON else CYAN_BRIGHT
        dim = "#b45309" if self._state == OverlayState.ENDING_SOON else CYAN_DIM

        for i, level in enumerate(bars):
            x0 = i * bar_w
            x1 = x0 + bar_w - gap
            bh = max(2, int(level * (h - 2)))
            color = dim if split >= 0 and i < split else bright
            c.create_rectangle(x0, h - bh, x1, h, fill=color, outline="")

        if split >= 0:
            sx = split * bar_w
            c.create_line(sx, 0, sx, h, fill="#ffffff", width=1)

        if self._state == OverlayState.ENDING_SOON and self._progress and self._timer_provider:
            try:
                elapsed_s, max_s = self._timer_provider()
                frac = min(1.0, elapsed_s / max_s) if max_s > 0 else 0
            except Exception:
                frac = 0
            pw = max(10, self._progress.winfo_width())
            self._progress.delete("all")
            self._progress.create_rectangle(0, 0, int(pw * frac), 3, fill="#f59e0b", outline="")


# Backward-compatible alias during migration
PartialOverlay = StatusOverlay