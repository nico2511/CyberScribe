"""Status overlay bar and testable UI logic (no dictated text in strings here)."""

from __future__ import annotations

import math
import struct
import threading
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, List, Optional, Sequence, Tuple

from overlay_placement import OVERLAY_BOTTOM_MARGIN_PX, WorkArea, compute_overlay_xy, query_primary_work_area

if TYPE_CHECKING:
    import tkinter as tk

BG_DARK = "#0b1120"
ACCENT_CYAN = "#00f2ff"
CYAN_DIM = "#0e7490"
CYAN_BRIGHT = "#00f2ff"
LISTEN_RED = "#e11d48"
OVERLAY_W = 420
OVERLAY_H = 38
BAR_COUNT = 48
VU_REFRESH_MS = 40
ENDING_SOON_SECONDS = 3
PASTED_HIDE_MS = 1500
TRANSITION_MS = 200
TRANSITION_STEP_MS = 40

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


def _hex_to_rgb(color: str) -> Tuple[int, int, int]:
    color = (color or "#000000").strip()
    if color.startswith("#"):
        color = color[1:]
    if len(color) != 6:
        return (0, 0, 0)
    return tuple(int(color[i : i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def _rgb_to_hex(rgb: Tuple[int, int, int]) -> str:
    return "#%02x%02x%02x" % tuple(max(0, min(255, int(v))) for v in rgb)


def lerp_hex_color(color_a: str, color_b: str, t: float) -> str:
    t = max(0.0, min(1.0, float(t)))
    a = _hex_to_rgb(color_a)
    b = _hex_to_rgb(color_b)
    mixed = tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3))
    return _rgb_to_hex(mixed)


def interpolate_palette(
    src: OverlayPalette, dst: OverlayPalette, t: float
) -> OverlayPalette:
    return OverlayPalette(
        border=lerp_hex_color(src.border, dst.border, t),
        pill_bg=lerp_hex_color(src.pill_bg, dst.pill_bg, t),
        pill_fg=lerp_hex_color(src.pill_fg, dst.pill_fg, t),
        detail_fg=lerp_hex_color(src.detail_fg, dst.detail_fg, t),
    )


STATE_PALETTE = {
    OverlayState.LISTENING: OverlayPalette(LISTEN_RED, LISTEN_RED, "#ffffff", ACCENT_CYAN),
    OverlayState.ENDING_SOON: OverlayPalette("#f59e0b", "#f59e0b", "#111827", "#fbbf24"),
    OverlayState.TRANSCRIBING: OverlayPalette(ACCENT_CYAN, ACCENT_CYAN, "#0b1120", "#94a3b8"),
    OverlayState.PASTED: OverlayPalette("#22c55e", "#22c55e", "#0b1120", "#bbf7d0"),
    OverlayState.ERROR: OverlayPalette("#f43f5e", "#be123c", "#ffffff", "#fecdd3"),
    OverlayState.CANCELLED: OverlayPalette("#6b7280", "#4b5563", "#e5e7eb", "#9ca3af"),
}


@dataclass(frozen=True)
class RecordingDisplayTick:
    state: OverlayState
    pill_text: str
    timer_text: str
    progress_frac: float


def format_record_timer(elapsed_s: float, max_s: int) -> str:
    elapsed_s = max(0.0, float(elapsed_s))
    max_s = max(0, int(max_s))

    def _part(seconds: float) -> str:
        whole = int(seconds)
        return f"{whole // 60}:{whole % 60:02d}"

    if max_s <= 0:
        return _part(elapsed_s)
    return f"{_part(elapsed_s)} / {_part(max_s)}"


def format_pasted_detail(char_count: int, dictation_s: float) -> str:
    char_count = max(0, int(char_count))
    dictation_s = max(0.0, float(dictation_s))
    if dictation_s < 10:
        dur = f"{dictation_s:.1f}".replace(".", ",")
    else:
        dur = str(int(round(dictation_s)))
    return f"{char_count} caractères · {dur} s"


def ending_soon_remaining(elapsed_s: float, max_s: int, threshold: int = ENDING_SOON_SECONDS) -> Optional[int]:
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


def recording_display_tick(
    elapsed_s: float,
    max_s: int,
    *,
    _current: Optional[OverlayState] = None,
) -> RecordingDisplayTick:
    """Pure update for chrono / pill / progress during listening (each vu tick)."""
    del _current
    remaining = ending_soon_remaining(elapsed_s, max_s)
    if remaining:
        state = OverlayState.ENDING_SOON
        pill = f"● Fin dans {remaining} s"
    else:
        state = OverlayState.LISTENING
        pill = "● Écoute"
    timer = format_record_timer(elapsed_s, max_s)
    frac = min(1.0, elapsed_s / max_s) if max_s > 0 else 0.0
    return RecordingDisplayTick(state, pill, timer, frac)


def pcm16_chunk_rms(chunk: bytes) -> float:
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


def scale_vu_level(raw_rms: float) -> float:
    """Map raw PCM RMS (often 0.01–0.12 for speech) to 0..1 bar height."""
    raw_rms = max(0.0, float(raw_rms))
    boosted = min(1.0, raw_rms * 18.0)
    return boosted ** 0.55


def vu_bar_height(display_level: float, canvas_h: int) -> int:
    display_level = max(0.0, min(1.0, float(display_level)))
    canvas_h = max(4, int(canvas_h))
    return max(2, int(display_level * (canvas_h - 2)))


def vu_meter_bar_levels(
    history: Sequence[float],
    *,
    pre_buffer_bars: int,
) -> Tuple[List[float], int]:
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


def tray_status_line(state: str, model_size: str, device: str, profile: str) -> str:
    profile_short = profile if profile in ("fast", "balanced", "accurate") else "fast"
    return f"{state} · {model_size} · {device} · {profile_short}"


def overlay_geometry_for_master(master, overlay_w: int = OVERLAY_W, overlay_h: int = OVERLAY_H) -> Tuple[int, int, int, int]:
    """Return ``width x height + x + y`` using work area when possible."""
    margin = OVERLAY_BOTTOM_MARGIN_PX
    work = query_primary_work_area()
    if work is None:
        sw = int(master.winfo_screenwidth())
        sh = int(master.winfo_screenheight())
        work = WorkArea(0, 0, sw, sh)
    x, y = compute_overlay_xy(work, overlay_w=overlay_w, overlay_h=overlay_h, margin=margin)
    return overlay_w, overlay_h, x, y


class StatusOverlay:
    """Bottom status bar overlay (~400×38). Updates must run on the Tk main thread."""

    def __init__(self, master):
        import tkinter as tk

        self._tk = tk
        self.master = master
        self.window = None
        self._inner = None
        self._pill = None
        self._body = None
        self._vu_row = None
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
        self._applied_palette: Optional[OverlayPalette] = None
        self._transition_after_id: Optional[str] = None
        self._pending_pill_text: Optional[str] = None

    def set_level_provider(self, provider):
        self._level_provider = provider

    def set_timer_provider(self, provider):
        self._timer_provider = provider

    def _ensure_window(self):
        tk = self._tk
        if self.window:
            return
        self.window = tk.Toplevel(self.master)
        self.window.overrideredirect(True)
        self.window.attributes("-topmost", True)
        self.window.attributes("-alpha", 0.95)

        ow, oh, x, y = overlay_geometry_for_master(self.master)
        self.window.geometry(f"{ow}x{oh}+{x}+{y}")

        self._inner = tk.Frame(self.window, bg=BG_DARK)
        self._inner.pack(fill="both", expand=True, padx=1, pady=1)

        self._pill = tk.Label(
            self._inner,
            text="",
            font=("Segoe UI Semibold", 10),
            anchor="w",
            padx=10,
            pady=2,
        )
        self._pill.pack(side="left", fill="y")

        self._body = tk.Frame(self._inner, bg=BG_DARK)
        self._body.pack(side="left", fill="both", expand=True, padx=(4, 6), pady=2)

        self._vu_row = tk.Frame(self._body, bg=BG_DARK)
        self._vu_row.columnconfigure(0, weight=1)
        self._vu_row.columnconfigure(1, weight=0, minsize=96)
        self._canvas = tk.Canvas(self._vu_row, height=22, bg=BG_DARK, highlightthickness=0)
        self._canvas.grid(row=0, column=0, sticky="ew")
        self._timer = tk.Label(
            self._vu_row,
            text="0:00 / 0:25",
            font=("Consolas", 10),
            bg=BG_DARK,
            anchor="e",
            width=11,
        )
        self._timer.grid(row=0, column=1, sticky="e", padx=(6, 0))

        self._progress = tk.Canvas(self._body, height=2, bg=BG_DARK, highlightthickness=0)

        self._detail = tk.Label(
            self._body,
            text="",
            font=("Segoe UI", 9),
            bg=BG_DARK,
            anchor="w",
        )

    def _cancel_timers(self):
        self._cancel_palette_transition()
        for attr in ("_hide_after_id", "_tick_after_id"):
            aid = getattr(self, attr)
            if aid and self.window:
                try:
                    self.window.after_cancel(aid)
                except Exception:
                    pass
            setattr(self, attr, None)

    def _apply_palette_direct(self, pal: OverlayPalette, *, pill_text: Optional[str] = None):
        if not self.window:
            return
        self.window.config(bg=pal.border)
        if self._inner:
            self._inner.config(bg=BG_DARK)
        if self._pill:
            self._pill.config(bg=pal.pill_bg, fg=pal.pill_fg)
            if pill_text is not None:
                self._pill.config(text=pill_text)
        if self._detail:
            self._detail.config(fg=pal.detail_fg, bg=BG_DARK)
        if self._timer:
            self._timer.config(fg=pal.detail_fg, bg=BG_DARK)
        self._applied_palette = pal

    def _cancel_palette_transition(self):
        if self._transition_after_id and self.window:
            try:
                self.window.after_cancel(self._transition_after_id)
            except Exception:
                pass
        self._transition_after_id = None

    def _apply_palette(self, state: OverlayState, *, pill_text: Optional[str] = None):
        pal = STATE_PALETTE.get(state)
        if not pal or not self.window:
            return
        start = self._applied_palette or pal
        if start.border == pal.border and start.pill_bg == pal.pill_bg:
            self._apply_palette_direct(pal, pill_text=pill_text)
            return

        steps = max(1, TRANSITION_MS // TRANSITION_STEP_MS)
        self._cancel_palette_transition()
        self._pending_pill_text = pill_text
        hold_text = pill_text
        if self._pill and hold_text is not None:
            self._pill.config(fg=lerp_hex_color(start.pill_fg, BG_DARK, 0.35))

        def _step(i=0):
            if not self.window:
                return
            t = (i + 1) / steps
            mid = interpolate_palette(start, pal, t)
            pt = hold_text if t >= 0.55 else None
            self._apply_palette_direct(mid, pill_text=pt)
            if i + 1 >= steps:
                self._apply_palette_direct(pal, pill_text=hold_text)
                self._transition_after_id = None
                return
            self._transition_after_id = self.window.after(TRANSITION_STEP_MS, lambda: _step(i + 1))

        _step(0)

    def _show_recording_layout(self):
        if self._detail:
            self._detail.pack_forget()
        if self._vu_row:
            self._vu_row.pack(fill="both", expand=True)

    def _show_detail_layout(self):
        if self._vu_row:
            self._vu_row.pack_forget()
        if self._progress:
            self._progress.pack_forget()
        if self._detail:
            self._detail.pack(fill="both", expand=True)

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
        self._pre_buffer_bars = pre_buffer_bar_count(pre_buffer_ms)
        self._apply_palette(state, pill_text=pill_text)
        if self.window:
            self.window.update_idletasks()

        show_vu = state in (OverlayState.LISTENING, OverlayState.ENDING_SOON)
        if show_vu:
            self._show_recording_layout()
            if self._timer:
                self._timer.config(text=timer_text or "0:00 / 0:25")
            if state == OverlayState.ENDING_SOON and self._progress:
                self._progress.pack(fill="x")
            elif self._progress:
                self._progress.pack_forget()
            self._start_vu_tick()
        else:
            self._stop_vu_tick()
            self._show_detail_layout()
            if self._detail:
                self._detail.config(text=detail_text)
            if self._canvas:
                self._canvas.delete("all")

        if auto_hide_ms and self.window:
            self._hide_after_id = self.window.after(auto_hide_ms, self.hide)

    def hide(self):
        self._cancel_timers()
        self._stop_vu_tick()
        self._state = OverlayState.HIDDEN
        self._vu_history.clear()
        self._applied_palette = None
        if self.window:
            try:
                self.window.destroy()
            except Exception:
                pass
        self.window = None
        self._inner = None
        self._pill = None
        self._body = None
        self._vu_row = None
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
                level = scale_vu_level(level)
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

        tick = recording_display_tick(elapsed_s, max_s)
        if tick.state != self._state:
            self._state = tick.state
            self._apply_palette(tick.state, pill_text=tick.pill_text)
            if tick.state == OverlayState.ENDING_SOON and self._progress:
                self._progress.pack(fill="x")
            elif self._progress:
                self._progress.pack_forget()

        if self._pill:
            self._pill.config(text=tick.pill_text)
        if self._timer:
            self._timer.config(text=tick.timer_text)

        self._draw_vu_meter(tick.progress_frac)
        if self.window:
            self._tick_after_id = self.window.after(VU_REFRESH_MS, self._vu_tick)

    def _draw_vu_meter(self, progress_frac: float = 0.0):
        if not self._canvas:
            return
        c = self._canvas
        c.delete("all")
        c.update_idletasks()
        w = max(80, c.winfo_width())
        h = max(10, c.winfo_height())
        with self._lock:
            bars, split = vu_meter_bar_levels(self._vu_history, pre_buffer_bars=self._pre_buffer_bars)
        bar_w = max(2, w // BAR_COUNT)
        gap = 1
        bright = "#fbbf24" if self._state == OverlayState.ENDING_SOON else CYAN_BRIGHT
        dim = "#b45309" if self._state == OverlayState.ENDING_SOON else CYAN_DIM

        for i, level in enumerate(bars):
            x0 = i * bar_w
            x1 = x0 + bar_w - gap
            bh = vu_bar_height(level, h)
            color = dim if split >= 0 and i < split else bright
            c.create_rectangle(x0, h - bh, x1, h, fill=color, outline="")

        if split >= 0:
            sx = split * bar_w
            c.create_line(sx, 0, sx, h, fill="#ffffff", width=1)

        if self._state == OverlayState.ENDING_SOON and self._progress:
            pw = max(10, self._progress.winfo_width())
            self._progress.delete("all")
            self._progress.create_rectangle(
                0,
                0,
                int(pw * min(1.0, progress_frac)),
                2,
                fill="#f59e0b",
                outline="",
            )


PartialOverlay = StatusOverlay