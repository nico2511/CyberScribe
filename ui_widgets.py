"""Custom Tk widgets matching CyberScribe UI mockups (no CyberScribe import)."""

from __future__ import annotations

import tkinter as tk
from typing import Callable, Dict, List, Optional, Sequence

from ui_theme import (
    C_ACCENT,
    C_BG,
    C_CARD_BORDER,
    C_CARD_SELECTED,
    C_CARD_SELECTED_BG,
    C_FOOTER_BTN_FG,
    C_INPUT_BG,
    C_INPUT_FG,
    C_MUTED,
    C_TEXT,
    CONTENT_PADX,
    FONT_HEADER_MONO,
    FONT_MONO,
    FONT_MONO_SMALL,
    FONT_UI,
    FONT_UI_BOLD,
    FONT_UI_SECTION,
    FONT_UI_SMALL,
    PROFILE_CARD_COPY,
)


def section_header(parent, title: str, help_text: str = "", *, help_lines: Optional[Sequence[str]] = None):
    tk.Label(parent, text=title, bg=C_BG, fg=C_ACCENT, font=FONT_UI_SECTION, anchor="w").pack(
        fill="x", padx=CONTENT_PADX, pady=(16, 2)
    )
    lines = list(help_lines) if help_lines else ([help_text] if help_text else [])
    for line in lines:
        if line:
            tk.Label(
                parent,
                text=line,
                bg=C_BG,
                fg=C_MUTED,
                font=FONT_UI_SMALL,
                anchor="w",
                justify="left",
            ).pack(fill="x", padx=CONTENT_PADX, pady=(0, 2))


def horiz_rule(parent, *, color=C_ACCENT, height=2, pady=(8, 12)):
    tk.Frame(parent, bg=color, height=height).pack(fill="x", padx=CONTENT_PADX, pady=pady)


def muted_rule(parent, pady=(0, 8)):
    tk.Frame(parent, bg=C_CARD_BORDER, height=1).pack(fill="x", padx=CONTENT_PADX, pady=pady)


def outline_button(parent, text: str, command: Callable, *, padx=12):
    return tk.Button(
        parent,
        text=text,
        command=command,
        bg=C_BG,
        fg=C_TEXT,
        font=FONT_UI_SMALL,
        relief="solid",
        bd=1,
        highlightbackground=C_CARD_BORDER,
        highlightthickness=1,
        activebackground=C_INPUT_BG,
        activeforeground=C_TEXT,
        padx=padx,
        pady=6,
        cursor="hand2",
    )


def solid_accent_button(parent, text: str, command: Callable):
    return tk.Button(
        parent,
        text=text,
        command=command,
        bg=C_ACCENT,
        fg=C_FOOTER_BTN_FG,
        font=FONT_UI_BOLD,
        relief="flat",
        activebackground=C_ACCENT,
        activeforeground=C_FOOTER_BTN_FG,
        padx=18,
        pady=8,
        cursor="hand2",
    )


def dark_entry(parent, textvariable, *, width=8, mono=True):
    font = FONT_MONO if mono else FONT_UI
    entry = tk.Entry(
        parent,
        textvariable=textvariable,
        width=width,
        bg=C_INPUT_BG,
        fg=C_INPUT_FG,
        insertbackground=C_ACCENT,
        font=font,
        relief="flat",
        highlightthickness=1,
        highlightbackground=C_CARD_BORDER,
        highlightcolor=C_ACCENT,
    )
    return entry


class DarkDropdown(tk.Frame):
    """Dark combobox (#1e293b, cyan text) without ttk."""

    def __init__(self, parent, variable: tk.StringVar, values: List[str], width: int = 22):
        super().__init__(parent, bg=C_INPUT_BG, highlightbackground=C_CARD_BORDER, highlightthickness=1)
        self._var = variable
        self._values = values
        self._menu: Optional[tk.Menu] = None

        inner = tk.Frame(self, bg=C_INPUT_BG)
        inner.pack(fill="both", expand=True, padx=6, pady=5)
        self._label = tk.Label(
            inner,
            textvariable=variable,
            bg=C_INPUT_BG,
            fg=C_INPUT_FG,
            font=FONT_UI,
            anchor="w",
            width=width,
        )
        self._label.pack(side="left", fill="x", expand=True)
        tk.Label(inner, text="▾", bg=C_INPUT_BG, fg=C_INPUT_FG, font=FONT_UI_SMALL).pack(side="right")

        for widget in (self, inner, self._label):
            widget.bind("<Button-1>", self._open_menu, add="+")

    def _open_menu(self, _event=None):
        if self._menu:
            self._menu.destroy()
        self._menu = tk.Menu(self, tearoff=0, bg=C_INPUT_BG, fg=C_TEXT, activebackground=C_CARD_BORDER)
        for value in self._values:
            self._menu.add_command(label=value, command=lambda v=value: self._var.set(v))
        x = self.winfo_rootx()
        y = self.winfo_rooty() + self.winfo_height()
        self._menu.tk_popup(x, y)


class TabStrip:
    def __init__(self, parent, names: Sequence[str], frames: Dict[str, tk.Frame]):
        self._names = list(names)
        self._frames = frames
        self._active = names[0] if names else ""
        self._labels: Dict[str, tk.Label] = {}
        self._underlines: Dict[str, tk.Frame] = {}

        bar = tk.Frame(parent, bg=C_BG)
        bar.pack(fill="x", padx=CONTENT_PADX, pady=(4, 0))
        for name in names:
            cell = tk.Frame(bar, bg=C_BG)
            cell.pack(side="left", padx=(0, 20))
            lbl = tk.Label(
                cell,
                text=name,
                bg=C_BG,
                fg=C_MUTED,
                font=FONT_UI_BOLD,
                cursor="hand2",
            )
            lbl.pack()
            ul = tk.Frame(cell, bg=C_BG, height=2)
            ul.pack(fill="x", pady=(4, 0))
            lbl.bind("<Button-1>", lambda e, n=name: self.select(n))
            self._labels[name] = lbl
            self._underlines[name] = ul
        muted_rule(parent, pady=(0, 4))
        self.select(self._active)

    def select(self, name: str):
        self._active = name
        for n, frame in self._frames.items():
            if n == name:
                frame.pack(fill="both", expand=True)
            else:
                frame.pack_forget()
        for n, lbl in self._labels.items():
            active = n == name
            lbl.config(fg=C_ACCENT if active else C_MUTED)
            self._underlines[n].config(bg=C_ACCENT if active else C_BG, height=2 if active else 1)


def build_profile_cards(parent, profile_var: tk.StringVar, on_select: Callable[[str], None]):
    row = tk.Frame(parent, bg=C_BG)
    row.pack(fill="x", padx=CONTENT_PADX - 4, pady=6)
    cards = {}

    def refresh(*_):
        sel = profile_var.get()
        for key, (card, inner, labels) in cards.items():
            selected = key == sel
            bg = C_CARD_SELECTED_BG if selected else C_INPUT_BG
            card.config(
                highlightbackground=C_CARD_SELECTED if selected else C_CARD_BORDER,
                highlightthickness=2,
            )
            inner.config(bg=bg)
            for lbl in labels:
                lbl.config(bg=bg)

    for key, (title, desc) in PROFILE_CARD_COPY.items():
        card = tk.Frame(row, bg=C_BG, highlightthickness=2, highlightbackground=C_CARD_BORDER)
        card.pack(side="left", fill="both", expand=True, padx=4)
        inner = tk.Frame(card, bg=C_INPUT_BG)
        inner.pack(fill="both", expand=True, padx=1, pady=1)

        def handler(k=key):
            def _go(_e=None):
                profile_var.set(k)
                on_select(k)

            return _go

        for w in (card, inner):
            w.bind("<Button-1>", handler())
        title_lbl = tk.Label(inner, text=title, bg=C_INPUT_BG, fg=C_TEXT, font=FONT_UI_BOLD, anchor="w")
        title_lbl.pack(anchor="w", padx=10, pady=(10, 2))
        desc_lbl = tk.Label(
            inner,
            text=desc,
            bg=C_INPUT_BG,
            fg=C_MUTED,
            font=FONT_UI_SMALL,
            anchor="w",
            justify="left",
        )
        desc_lbl.pack(anchor="w", padx=10, pady=(0, 10))
        cards[key] = (card, inner, [title_lbl, desc_lbl])

    profile_var.trace_add("write", refresh)
    refresh()
    return cards


class PreBufferCanvas(tk.Canvas):
    """Custom 0–3 s slider with cyan fill and square handle."""

    def __init__(self, parent, variable: tk.DoubleVar, on_change: Optional[Callable[[], None]] = None):
        super().__init__(parent, bg=C_BG, height=52, highlightthickness=0, cursor="hand2")
        self._var = variable
        self._on_change = on_change
        self._drag = False
        self._value_lbl: Optional[tk.Label] = None
        self.bind("<Configure>", lambda e: self._draw())
        self.bind("<Button-1>", self._press)
        self.bind("<B1-Motion>", self._drag_motion)
        self.bind("<ButtonRelease-1>", self._release)
        variable.trace_add("write", lambda *_: self._draw())

    def attach_value_label(self, label: tk.Label):
        self._value_lbl = label

    def _margins(self):
        return 8, max(40, self.winfo_width()) - 8

    def _pos_to_value(self, x):
        x0, x1 = self._margins()
        span = max(1, x1 - x0)
        t = max(0.0, min(1.0, (x - x0) / span))
        raw = t * 3.0
        return round(raw * 2) / 2.0

    def _value_to_x(self, val):
        x0, x1 = self._margins()
        return x0 + (val / 3.0) * (x1 - x0)

    def _press(self, event):
        self._drag = True
        self._var.set(self._pos_to_value(event.x))

    def _drag_motion(self, event):
        if self._drag:
            self._var.set(self._pos_to_value(event.x))

    def _release(self, _event):
        self._drag = False
        if self._on_change:
            self._on_change()

    def _draw(self):
        self.delete("all")
        w = max(120, self.winfo_width())
        self.config(width=w)
        y_track = 20
        x0, x1 = self._margins()
        val = float(self._var.get())
        hx = self._value_to_x(val)
        self.create_line(x0, y_track, x1, y_track, fill=C_CARD_BORDER, width=2)
        if val > 0:
            self.create_line(x0, y_track, hx, y_track, fill=C_ACCENT, width=2)
        size = 11
        self.create_rectangle(
            hx - size / 2,
            y_track - size / 2,
            hx + size / 2,
            y_track + size / 2,
            outline=C_ACCENT,
            fill=C_BG,
            width=2,
        )
        for label, frac in (("off", 0.0), ("1 s", 1 / 3), ("2 s", 2 / 3), ("3 s", 1.0)):
            tx = x0 + frac * (x1 - x0)
            self.create_text(tx, y_track + 18, text=label, fill=C_MUTED, font=FONT_UI_SMALL)
        if self._value_lbl:
            if val <= 0.05:
                self._value_lbl.config(text="off")
            else:
                self._value_lbl.config(text=f"{val:.1f}".replace(".", ",") + " s")


def config_shell(parent, title: str, status_text: str) -> tuple[tk.Frame, tk.Frame]:
    """Return (outer, content_host) with header and rules."""
    outer = tk.Frame(parent, bg=C_BG)
    outer.pack(fill="both", expand=True, padx=2, pady=2)
    header = tk.Frame(outer, bg=C_BG)
    header.pack(fill="x", padx=CONTENT_PADX, pady=(14, 6))
    tk.Label(header, text=title, bg=C_BG, fg=C_ACCENT, font=FONT_HEADER_MONO, anchor="w").pack(side="left")
    tk.Label(header, text=status_text, bg=C_BG, fg=C_MUTED, font=FONT_MONO_SMALL, anchor="e").pack(side="right")
    horiz_rule(outer, pady=(0, 8))
    host = tk.Frame(outer, bg=C_BG)
    host.pack(fill="both", expand=True)
    return outer, host


def config_footer(parent, *, on_test: Callable, on_save: Callable) -> tk.Frame:
    muted_rule(parent, pady=(8, 12))
    footer = tk.Frame(parent, bg=C_BG)
    footer.pack(fill="x", padx=CONTENT_PADX, pady=(0, 14))
    left = tk.Frame(footer, bg=C_BG)
    left.pack(side="left", anchor="sw")
    for line in ("Les modifications", "s'appliquent", "à l'enregistrement."):
        tk.Label(left, text=line, bg=C_BG, fg=C_MUTED, font=FONT_UI_SMALL, anchor="w").pack(anchor="w")
    right = tk.Frame(footer, bg=C_BG)
    right.pack(side="right")
    outline_button(right, "[ TESTER LA DICTÉE ]", on_test, padx=14).pack(side="left", padx=(0, 12))
    solid_accent_button(right, ">> ENREGISTRER <<", on_save).pack(side="left")
    return footer