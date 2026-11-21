"""First-run guided wizard (3 steps). Does not import CyberScribe."""

from __future__ import annotations

import tkinter as tk

from audio_devices import enumerate_input_devices
from cyber_config import DEFAULT_CONFIG
from hotkey_util import display_hotkey
from overlay_ui import scale_vu_level, vu_bar_height
from ui_theme import (
    C_ACCENT,
    C_BG,
    C_CARD_BORDER,
    C_CARD_SELECTED,
    C_CARD_SELECTED_BG,
    C_INPUT_BG,
    C_INPUT_FG,
    C_MUTED,
    C_TEXT,
    CONTENT_PADX,
    FIRST_RUN_HEIGHT,
    FIRST_RUN_WIDTH,
    FONT_HEADER_MONO,
    FONT_MONO,
    FONT_TITLE,
    FONT_UI,
    FONT_UI_BOLD,
    FONT_UI_SMALL,
    MODEL_CARD_COPY,
)
from ui_widgets import DarkDropdown, dark_entry, horiz_rule, muted_rule, outline_button, solid_accent_button


def maybe_show_first_run(app):
    if app.config.get("first_run_done"):
        return
    if app.first_run_window and app.first_run_window.winfo_exists():
        return
    open_first_run_wizard(app)


def open_first_run_wizard(app):
    root = tk.Toplevel(app.root)
    app.first_run_window = root
    root.title("Bienvenue dans CyberScribe")
    root.configure(bg=C_ACCENT)
    ws, hs = root.winfo_screenwidth(), root.winfo_screenheight()
    root.geometry(f"{FIRST_RUN_WIDTH}x{FIRST_RUN_HEIGHT}+{(ws - FIRST_RUN_WIDTH) // 2}+{(hs - FIRST_RUN_HEIGHT) // 2}")
    root.minsize(FIRST_RUN_WIDTH, 520)
    root.attributes("-topmost", True)
    root.after(200, lambda: root.attributes("-topmost", False))

    outer = tk.Frame(root, bg=C_BG)
    outer.pack(fill="both", expand=True, padx=2, pady=2)

    header = tk.Frame(outer, bg=C_BG)
    header.pack(fill="x", padx=CONTENT_PADX, pady=(14, 6))
    tk.Label(header, text="/// Mise en route", bg=C_BG, fg=C_ACCENT, font=FONT_HEADER_MONO).pack(side="left")
    step_label = tk.Label(header, text="étape 1 sur 3", bg=C_BG, fg=C_MUTED, font=FONT_MONO)
    step_label.pack(side="right")
    horiz_rule(outer, pady=(0, 6))

    nav = tk.Frame(outer, bg=C_BG)
    nav.pack(fill="x", padx=CONTENT_PADX, pady=(0, 4))
    steps = ["Micro", "Vitesse", "Essai avec F8"]
    step_labels = []

    def _refresh_nav(active: int):
        for i, lbl in enumerate(step_labels):
            done = i < active
            is_active = i == active
            if done:
                lbl.config(text=f"✓ {steps[i]}", fg=C_MUTED)
            elif is_active:
                lbl.config(text=steps[i], fg=C_ACCENT)
            else:
                lbl.config(text=steps[i], fg=C_MUTED)
        for i, bar in enumerate(step_bars):
            if i < active:
                bar.config(bg=C_MUTED, height=2)
            elif i == active:
                bar.config(bg=C_ACCENT, height=3)
            else:
                bar.config(bg=C_CARD_BORDER, height=2)

    step_bars = []
    for name in steps:
        col = tk.Frame(nav, bg=C_BG)
        col.pack(side="left", expand=True, fill="x", padx=2)
        lbl = tk.Label(col, text=name, bg=C_BG, fg=C_MUTED, font=FONT_UI_SMALL)
        lbl.pack()
        step_labels.append(lbl)
        bar = tk.Frame(col, bg=C_CARD_BORDER, height=2)
        bar.pack(fill="x", pady=(4, 0))
        step_bars.append(bar)
    muted_rule(outer)

    body = tk.Frame(outer, bg=C_BG)
    body.pack(fill="both", expand=True, padx=CONTENT_PADX, pady=4)

    footer = tk.Frame(outer, bg=C_BG)
    footer.pack(fill="x", padx=CONTENT_PADX, pady=(8, 14))
    note_frame = tk.Frame(footer, bg=C_BG)
    note_frame.pack(side="left", anchor="sw")
    note_l1 = tk.Label(note_frame, text="Modifiable plus tard", bg=C_BG, fg=C_MUTED, font=FONT_UI_SMALL, anchor="w")
    note_l1.pack(anchor="w")
    note_l2 = tk.Label(note_frame, text="dans Configuration → Moteur.", bg=C_BG, fg=C_MUTED, font=FONT_UI_SMALL, anchor="w")
    note_l2.pack(anchor="w")

    state = {"step": 0}
    vu_after = {"id": None}

    def _finish_later():
        app.config.set("first_run_done", True)
        try:
            root.destroy()
        except Exception:
            pass
        app.first_run_window = None

    def _go_next():
        if state["step"] < 2:
            state["step"] += 1
            _render_step()
            return
        app.config.set("first_run_done", True)
        try:
            root.destroy()
        except Exception:
            pass
        app.first_run_window = None

    btn_row = tk.Frame(footer, bg=C_BG)
    btn_row.pack(side="right")
    outline_button(btn_row, "[ PLUS TARD ]", _finish_later, padx=14).pack(side="left", padx=(0, 12))
    solid_accent_button(btn_row, ">> CONTINUER <<", _go_next).pack(side="left")

    def _clear_body():
        if vu_after["id"]:
            try:
                root.after_cancel(vu_after["id"])
            except Exception:
                pass
            vu_after["id"] = None
        for child in body.winfo_children():
            child.destroy()

    def _render_step():
        step = state["step"]
        step_label.config(text=f"étape {step + 1} sur 3")
        _refresh_nav(step)
        _clear_body()
        if step == 0:
            _build_micro_step()
        elif step == 1:
            _build_speed_step()
        else:
            _build_try_step()

    def _build_micro_step():
        tk.Label(body, text="Choisis ton micro", bg=C_BG, fg=C_TEXT, font=FONT_TITLE, anchor="w").pack(
            anchor="w", pady=(8, 4)
        )
        tk.Label(
            body,
            text="Parle pour voir le vu-mètre bouger.",
            bg=C_BG,
            fg=C_MUTED,
            font=FONT_UI_SMALL,
            anchor="w",
        ).pack(anchor="w", pady=(0, 12))
        devices = enumerate_input_devices(app.recorder.audio)
        names = [d.name for d in devices]
        mic_var = tk.StringVar(root)
        cur = app.config.get("input_device") or ""
        if cur in names:
            mic_var.set(cur)
        elif names:
            mic_var.set(names[0])
        dd = DarkDropdown(body, mic_var, names or ["(aucun)"])
        dd.pack(fill="x", pady=4)
        mic_var.trace_add("write", lambda *_: app.apply_input_device(mic_var.get().strip()))
        vu = tk.Canvas(body, height=36, bg=C_INPUT_BG, highlightthickness=1, highlightbackground=C_CARD_BORDER)
        vu.pack(fill="x", pady=12)

        def _vu():
            if not root.winfo_exists():
                return
            vu.delete("all")
            w = max(80, vu.winfo_width())
            h = max(10, vu.winfo_height())
            bh = vu_bar_height(scale_vu_level(app.recorder.get_audio_level()), h)
            vu.create_rectangle(0, h - bh, w, h, fill=C_ACCENT, outline="")
            vu_after["id"] = root.after(60, _vu)

        _vu()

    def _build_speed_step():
        tk.Label(body, text="Quelle vitesse veux-tu ?", bg=C_BG, fg=C_TEXT, font=FONT_TITLE, anchor="w").pack(
            anchor="w", pady=(8, 4)
        )
        tk.Label(
            body,
            text="Tout reste sur ton PC. Le modèle est téléchargé une seule fois,\nensuite CyberScribe fonctionne hors ligne.",
            bg=C_BG,
            fg=C_MUTED,
            font=FONT_UI_SMALL,
            justify="left",
            anchor="w",
        ).pack(anchor="w", pady=(0, 10))
        if app.has_nvidia:
            banner = tk.Frame(body, bg=C_INPUT_BG)
            banner.pack(fill="x", pady=(0, 12))
            tk.Frame(banner, bg=C_ACCENT, width=4).pack(side="left", fill="y")
            txt = tk.Label(
                banner,
                text=">> Carte NVIDIA détectée : la transcription utilisera ",
                bg=C_INPUT_BG,
                fg=C_TEXT,
                font=FONT_UI_SMALL,
            )
            txt.pack(side="left", padx=(10, 0), pady=8)
            tk.Label(banner, text="CUDA", bg=C_INPUT_BG, fg=C_ACCENT, font=FONT_UI_BOLD).pack(side="left", pady=8)
            tk.Label(banner, text=".", bg=C_INPUT_BG, fg=C_TEXT, font=FONT_UI_SMALL).pack(side="left", pady=8)

        model_var = tk.StringVar(root, value=app.config.get("model_size") or "base")
        card_models = {}
        radio_dots = {}

        def _pick_model(key):
            model_var.set(key)
            saved = app.config.get("model_size")
            if key != saved:
                app.config.set("model_size", key)
                app.transcriber.reload()
                app.update_tray_icon(state="loading")

        def _refresh_cards(*_):
            sel = model_var.get()
            for key, (card, inner, widgets) in card_models.items():
                selected = key == sel
                bg = C_CARD_SELECTED_BG if selected else C_INPUT_BG
                card.config(highlightbackground=C_CARD_SELECTED if selected else C_CARD_BORDER, highlightthickness=2)
                inner.config(bg=bg)
                for w in widgets:
                    w.config(bg=bg)

        for key in ("tiny", "base", "small"):
            title, line1, size = MODEL_CARD_COPY[key]
            card = tk.Frame(body, bg=C_BG, highlightthickness=2, highlightbackground=C_CARD_BORDER)
            card.pack(fill="x", pady=4)
            inner = tk.Frame(card, bg=C_INPUT_BG)
            inner.pack(fill="x", padx=1, pady=1)

            row = tk.Frame(inner, bg=inner["bg"])
            row.pack(fill="x", padx=10, pady=10)
            dot = tk.Canvas(row, width=18, height=18, bg=inner["bg"], highlightthickness=0)
            dot.pack(side="left", padx=(0, 10))

            mid = tk.Frame(row, bg=inner["bg"])
            mid.pack(side="left", fill="x", expand=True)
            t_lbl = tk.Label(mid, text=title, bg=inner["bg"], fg=C_TEXT, font=FONT_UI_BOLD, anchor="w")
            t_lbl.pack(anchor="w")
            s_lbl = tk.Label(mid, text=line1, bg=inner["bg"], fg=C_MUTED, font=FONT_UI_SMALL, anchor="w")
            s_lbl.pack(anchor="w")
            size_lbl = tk.Label(row, text=size, bg=inner["bg"], fg=C_INPUT_FG, font=FONT_MONO)
            size_lbl.pack(side="right")

            def _h(k=key):
                return lambda e=None: _pick_model(k)

            radio_dots[key] = dot
            for w in (card, inner, row, dot, t_lbl, s_lbl, size_lbl):
                w.bind("<Button-1>", _h())
            card_models[key] = (card, inner, [row, mid, t_lbl, s_lbl, size_lbl, dot])

        def _refresh_dots():
            sel = model_var.get()
            for key, dot in radio_dots.items():
                dot.delete("all")
                selected = key == sel
                dot.create_oval(2, 2, 16, 16, outline=C_ACCENT if selected else C_MUTED, width=2)
                if selected:
                    dot.create_oval(6, 6, 12, 12, fill=C_ACCENT, outline="")

        def _on_model_change(*_):
            _refresh_cards()
            _refresh_dots()

        model_var.trace_add("write", _on_model_change)
        _refresh_dots()
        _refresh_cards()
        _refresh_dots()

        progress_var = tk.StringVar(root, value="")
        tk.Label(body, textvariable=progress_var, bg=C_BG, fg=C_MUTED, font=FONT_MONO, anchor="w").pack(
            anchor="w", pady=(14, 4)
        )
        prog_canvas = tk.Canvas(body, height=6, bg=C_CARD_BORDER, highlightthickness=0)
        prog_canvas.pack(fill="x", pady=(0, 4))
        path_hint = app.config.get_models_dir() or "%LOCALAPPDATA%\\CyberScribe\\models"
        tk.Label(body, text=f"dans {path_hint}", bg=C_BG, fg=C_MUTED, font=FONT_MONO_SMALL, anchor="w").pack(anchor="w")

        def _poll_loading():
            if not root.winfo_exists():
                return
            prog_canvas.delete("all")
            w = max(60, prog_canvas.winfo_width())
            if app.transcriber.loading:
                frac = 0.62
                prog_canvas.create_rectangle(0, 0, int(w * frac), 6, fill=C_ACCENT, outline="")
                progress_var.set(
                    f"Téléchargement du modèle {model_var.get()} · {int(frac * 100)} % · "
                    f"{int(90)} / 145 Mo"
                )
            else:
                prog_canvas.create_rectangle(0, 0, w, 6, fill=C_ACCENT, outline="")
                progress_var.set(f"Modèle {model_var.get()} prêt.")
            root.after(400, _poll_loading)

        _poll_loading()

    def _build_try_step():
        hk = display_hotkey(app.config.get("hotkey"))
        tk.Label(body, text=f"Appuie sur {hk} et dis bonjour", bg=C_BG, fg=C_TEXT, font=FONT_TITLE, anchor="w").pack(
            anchor="w", pady=(8, 4)
        )
        tk.Label(
            body,
            text="Le texte transcrit apparaît ici (100 % local).",
            bg=C_BG,
            fg=C_MUTED,
            font=FONT_UI_SMALL,
            anchor="w",
        ).pack(anchor="w", pady=(0, 12))
        result_var = tk.StringVar(root, value="")
        dark_entry(body, result_var, width=56, mono=False).pack(fill="x", ipady=4)

        def _poll_result():
            if not root.winfo_exists():
                return
            sample = getattr(app, "_first_run_sample_text", "")
            if sample:
                result_var.set(sample)
            root.after(300, _poll_result)

        app._first_run_sample_text = ""
        _poll_result()

    _render_step()
    root.protocol("WM_DELETE_WINDOW", _finish_later)