"""First-run guided wizard (3 steps). Does not import CyberScribe."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from audio_devices import enumerate_input_devices
from cyber_config import DEFAULT_CONFIG
from hotkey_util import display_hotkey
from overlay_ui import scale_vu_level, vu_bar_height
from ui_theme import (
    C_ACCENT,
    C_BG,
    C_CARD_BORDER,
    C_CARD_SELECTED,
    C_INPUT_BG,
    C_INPUT_FG,
    C_MUTED,
    C_TEXT,
    FONT_MONO,
    FONT_UI,
    FONT_UI_BOLD,
    FONT_UI_SMALL,
    FONT_UI_TITLE,
    MODEL_CARD_COPY,
)


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
    w, h = 540, 620
    ws, hs = root.winfo_screenwidth(), root.winfo_screenheight()
    root.geometry(f"{w}x{h}+{(ws - w) // 2}+{(hs - h) // 2}")
    root.attributes("-topmost", True)
    root.after(200, lambda: root.attributes("-topmost", False))

    outer = tk.Frame(root, bg=C_BG)
    outer.pack(fill="both", expand=True, padx=2, pady=2)

    header = tk.Frame(outer, bg=C_BG)
    header.pack(fill="x", padx=20, pady=(14, 6))
    tk.Label(header, text="/// Mise en route", bg=C_BG, fg=C_ACCENT, font=FONT_UI_TITLE).pack(side="left")
    step_label = tk.Label(header, text="étape 1 sur 3", bg=C_BG, fg=C_MUTED, font=FONT_UI_SMALL)
    step_label.pack(side="right")

    nav = tk.Frame(outer, bg=C_BG)
    nav.pack(fill="x", padx=20, pady=(0, 8))
    steps = ["Micro", "Vitesse", "Essai avec F8"]
    step_indicators = []

    def _refresh_nav(active: int):
        for i, name in enumerate(steps):
            lbl, bar = step_indicators[i]
            done = i < active
            is_active = i == active
            if done:
                lbl.config(text=f"✓ {name}", fg=C_MUTED)
                bar.config(bg=C_MUTED, height=2)
            elif is_active:
                lbl.config(text=name, fg=C_ACCENT)
                bar.config(bg=C_ACCENT, height=3)
            else:
                lbl.config(text=name, fg=C_MUTED)
                bar.config(bg=C_CARD_BORDER, height=2)

    for name in steps:
        col = tk.Frame(nav, bg=C_BG)
        col.pack(side="left", expand=True, fill="x", padx=4)
        lbl = tk.Label(col, text=name, bg=C_BG, fg=C_MUTED, font=FONT_UI_SMALL)
        lbl.pack()
        bar = tk.Frame(col, bg=C_CARD_BORDER, height=2)
        bar.pack(fill="x", pady=(4, 0))
        step_indicators.append((lbl, bar))

    body = tk.Frame(outer, bg=C_BG)
    body.pack(fill="both", expand=True, padx=20, pady=4)

    footer = tk.Frame(outer, bg=C_BG)
    footer.pack(fill="x", padx=20, pady=(8, 16))
    note_var = tk.StringVar(
        root,
        value="Modifiable plus tard dans Configuration → Moteur.",
    )

    state = {"step": 0}

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

    tk.Button(
        footer,
        text="[ PLUS TARD ]",
        command=_finish_later,
        bg=C_BG,
        fg=C_TEXT,
        font=FONT_UI_SMALL,
        relief="solid",
        bd=1,
    ).pack(side="left")
    tk.Label(footer, textvariable=note_var, bg=C_BG, fg=C_MUTED, font=FONT_UI_SMALL).pack(side="left", padx=12)
    tk.Button(
        footer,
        text=">> CONTINUER <<",
        command=_go_next,
        bg=C_ACCENT,
        fg="#0f172a",
        font=FONT_UI_BOLD,
        relief="flat",
        padx=12,
        pady=6,
    ).pack(side="right")

    vu_after = {"id": None}

    # Step builders
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
        tk.Label(
            body,
            text="Choisis ton micro",
            bg=C_BG,
            fg=C_TEXT,
            font=("Segoe UI", 14, "bold"),
        ).pack(anchor="w", pady=(8, 4))
        tk.Label(
            body,
            text="Parle pour voir le vu-mètre bouger.",
            bg=C_BG,
            fg=C_MUTED,
            font=FONT_UI_SMALL,
            wraplength=460,
            justify="left",
        ).pack(anchor="w", pady=(0, 12))
        devices = enumerate_input_devices(app.recorder.audio)
        names = [d.name for d in devices]
        mic_var = tk.StringVar(root)
        cur = app.config.get("input_device") or ""
        if cur in names:
            mic_var.set(cur)
        elif names:
            mic_var.set(names[0])
        combo = ttk.Combobox(body, textvariable=mic_var, values=names, font=FONT_UI, state="readonly")
        combo.pack(anchor="w", fill="x", pady=4)

        def _on_mic(_e=None):
            app.apply_input_device(mic_var.get().strip())

        combo.bind("<<ComboboxSelected>>", _on_mic)

        vu = tk.Canvas(body, height=32, bg=C_INPUT_BG, highlightthickness=0, width=460)
        vu.pack(anchor="w", pady=12)

        def _vu():
            if not root.winfo_exists():
                return
            vu.delete("all")
            w = max(80, vu.winfo_width())
            h = max(10, vu.winfo_height())
            level = scale_vu_level(app.recorder.get_audio_level())
            bh = vu_bar_height(level, h)
            vu.create_rectangle(0, h - bh, w, h, fill=C_ACCENT, outline="")
            vu_after["id"] = root.after(60, _vu)

        _vu()
        note_var.set("Étape Micro — tu peux passer avec Plus tard.")

    def _build_speed_step():
        tk.Label(
            body,
            text="Quelle vitesse veux-tu ?",
            bg=C_BG,
            fg=C_TEXT,
            font=("Segoe UI", 14, "bold"),
        ).pack(anchor="w", pady=(8, 4))
        tk.Label(
            body,
            text="Tout reste sur ton PC. Le modèle est téléchargé une seule fois, ensuite CyberScribe fonctionne hors ligne.",
            bg=C_BG,
            fg=C_MUTED,
            font=FONT_UI_SMALL,
            wraplength=460,
            justify="left",
        ).pack(anchor="w", pady=(0, 10))
        if app.has_nvidia:
            tk.Label(
                body,
                text=">> Carte NVIDIA détectée : la transcription utilisera CUDA.",
                bg=C_BG,
                fg=C_ACCENT,
                font=FONT_UI_SMALL,
                wraplength=460,
                justify="left",
            ).pack(anchor="w", pady=(0, 12))

        model_var = tk.StringVar(root, value=app.config.get("model_size") or "base")
        cards_row = tk.Frame(body, bg=C_BG)
        cards_row.pack(fill="x", pady=8)

        def _pick_model(key):
            model_var.set(key)

        card_models = {}

        def _refresh_cards(*_):
            sel = model_var.get()
            for k, c in card_models.items():
                c.config(highlightbackground=C_CARD_SELECTED if k == sel else C_CARD_BORDER)

        for key in ("tiny", "base", "small"):
            title, line1, size = MODEL_CARD_COPY[key]
            card = tk.Frame(cards_row, bg=C_BG, highlightthickness=2, highlightbackground=C_CARD_BORDER)
            card.pack(side="left", fill="both", expand=True, padx=4, ipady=6)
            card_models[key] = card

            def _h(k):
                return lambda e=None: _pick_model(k)

            card.bind("<Button-1>", _h(key))
            tk.Label(card, text=title, bg=C_BG, fg=C_TEXT, font=FONT_UI_BOLD).pack(pady=(6, 2))
            tk.Label(card, text=line1, bg=C_BG, fg=C_MUTED, font=FONT_UI_SMALL, wraplength=120).pack()
            tk.Label(card, text=size, bg=C_BG, fg=C_INPUT_FG, font=FONT_MONO).pack(pady=(4, 6))

        model_var.trace_add("write", _refresh_cards)
        _refresh_cards()

        progress_var = tk.StringVar(root, value="")
        tk.Label(body, textvariable=progress_var, bg=C_BG, fg=C_INPUT_FG, font=FONT_MONO, wraplength=460).pack(
            anchor="w", pady=(12, 4)
        )
        bar = ttk.Progressbar(body, mode="indeterminate", length=460)
        bar.pack(anchor="w", pady=4)
        path_hint = app.config.get_models_dir() or DEFAULT_CONFIG.get("models_dir") or "models"
        tk.Label(
            body,
            text=f"dans {path_hint}",
            bg=C_BG,
            fg=C_MUTED,
            font=FONT_UI_SMALL,
        ).pack(anchor="w")

        saved_model = app.config.get("model_size")

        def _apply_model():
            chosen = model_var.get()
            if chosen != saved_model:
                app.config.set("model_size", chosen)
                app.transcriber.reload()
                app.update_tray_icon(state="loading")

        _apply_model()

        def _poll_loading():
            if not root.winfo_exists():
                return
            if app.transcriber.loading:
                bar.start(12)
                progress_var.set(f"Téléchargement du modèle {model_var.get()}…")
            else:
                bar.stop()
                progress_var.set(f"Modèle {model_var.get()} prêt.")
            root.after(400, _poll_loading)

        _poll_loading()
        note_var.set("Modifiable plus tard dans Configuration → Moteur.")

    def _build_try_step():
        hk = display_hotkey(app.config.get("hotkey"))
        tk.Label(
            body,
            text=f"Appuie sur {hk} et dis bonjour",
            bg=C_BG,
            fg=C_TEXT,
            font=("Segoe UI", 14, "bold"),
        ).pack(anchor="w", pady=(8, 4))
        tk.Label(
            body,
            text="Le texte transcrit apparaît ici (100 % local).",
            bg=C_BG,
            fg=C_MUTED,
            font=FONT_UI_SMALL,
            wraplength=460,
            justify="left",
        ).pack(anchor="w", pady=(0, 12))
        result_var = tk.StringVar(root, value="")
        entry = tk.Entry(
            body,
            textvariable=result_var,
            bg=C_INPUT_BG,
            fg=C_INPUT_FG,
            font=FONT_UI,
            relief="flat",
            width=50,
        )
        entry.pack(fill="x", ipady=6)

        def _poll_result():
            if not root.winfo_exists():
                return
            sample = getattr(app, "_first_run_sample_text", "")
            if sample:
                result_var.set(sample)
            root.after(300, _poll_result)

        app._first_run_sample_text = ""
        _poll_result()
        note_var.set("Essai facultatif — Plus tard termine l'accueil.")

    _render_step()

    def _on_close():
        _finish_later()

    root.protocol("WM_DELETE_WINDOW", _on_close)