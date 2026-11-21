"""Configuration window (4 tabs, French UI). Does not import CyberScribe."""

from __future__ import annotations

import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from audio_devices import enumerate_input_devices
from audio_pre_buffer import clamp_pre_buffer_ms
from cyber_config import DEFAULT_CONFIG, VALID_LANGUAGES
from hotkey_util import display_hotkey, normalize_hotkey
from models_storage import (
    canonical_models_dir_config,
    directory_has_model_files,
    ensure_models_dir,
    migrate_models_directory,
    resolve_models_dir,
)
from overlay_ui import resolve_device_label, scale_vu_level, vu_bar_height
from ui_theme import (
    C_ACCENT,
    C_BG,
    C_CARD_BORDER,
    C_CARD_SELECTED,
    C_INPUT_BG,
    C_INPUT_FG,
    C_MUTED,
    C_TEXT,
    C_WARN,
    FONT_MONO,
    FONT_MONO_SMALL,
    FONT_UI,
    FONT_UI_BOLD,
    FONT_UI_SMALL,
    FONT_UI_TITLE,
    LANGUAGE_LABELS,
    PROFILE_CARD_COPY,
)


def open_settings_window(app):
    """Open or focus the tabbed configuration window on ``app``."""
    if app.settings_window and app.settings_window.winfo_exists():
        try:
            app.settings_window.lift()
            app.settings_window.focus_force()
            return
        except Exception:
            pass

    root = tk.Toplevel(app.root)
    app.settings_window = root
    root.title(f"CyberScribe — Configuration v{app.version}")
    root.configure(bg=C_ACCENT)

    width, height = 520, min(720, max(520, root.winfo_screenheight() - 100))
    ws, hs = root.winfo_screenwidth(), root.winfo_screenheight()
    x = (ws // 2) - (width // 2)
    y = max(20, (hs // 2) - (height // 2))
    root.geometry(f"{width}x{height}+{x}+{y}")
    root.minsize(480, 480)
    root.attributes("-topmost", True)
    root.after(100, lambda: root.attributes("-topmost", False))

    outer = tk.Frame(root, bg=C_BG)
    outer.pack(fill="both", expand=True, padx=2, pady=2)

    header = tk.Frame(outer, bg=C_BG)
    header.pack(fill="x", padx=16, pady=(12, 4))
    tk.Label(
        header,
        text="/// Configuration",
        bg=C_BG,
        fg=C_ACCENT,
        font=FONT_UI_TITLE,
    ).pack(side="left")
    status = app.tray_status_short()
    tk.Label(
        header,
        text=status,
        bg=C_BG,
        fg=C_MUTED,
        font=FONT_UI_SMALL,
    ).pack(side="right")

    notebook = ttk.Notebook(outer)
    notebook.pack(fill="both", expand=True, padx=8, pady=(4, 0))

    tab_dictee = tk.Frame(notebook, bg=C_BG)
    tab_micro = tk.Frame(notebook, bg=C_BG)
    tab_moteur = tk.Frame(notebook, bg=C_BG)
    tab_systeme = tk.Frame(notebook, bg=C_BG)
    notebook.add(tab_dictee, text="Dictée")
    notebook.add(tab_micro, text="Micro")
    notebook.add(tab_moteur, text="Moteur")
    notebook.add(tab_systeme, text="Système")

    style = ttk.Style(root)
    style.theme_use("clam")
    style.configure("TNotebook", background=C_BG, borderwidth=0)
    style.configure("TNotebook.Tab", background=C_BG, foreground=C_MUTED, font=FONT_UI_BOLD, padding=(12, 6))
    style.map(
        "TNotebook.Tab",
        background=[("selected", C_BG)],
        foreground=[("selected", C_ACCENT)],
    )
    style.configure(
        "TCombobox",
        fieldbackground=C_INPUT_BG,
        background=C_INPUT_BG,
        foreground=C_INPUT_FG,
    )

    # --- Dictée tab ---
    hk_var = tk.StringVar(root, value=normalize_hotkey(app.config.get("hotkey")))
    hk_display_var = tk.StringVar(root, value=display_hotkey(hk_var.get()))
    hk_status_var = tk.StringVar(root, value="")

    def section(parent, title, help_text=""):
        tk.Label(parent, text=title, bg=C_BG, fg=C_ACCENT, font=FONT_UI_BOLD).pack(
            anchor="w", padx=16, pady=(14, 2)
        )
        if help_text:
            tk.Label(
                parent,
                text=help_text,
                bg=C_BG,
                fg=C_MUTED,
                font=FONT_UI_SMALL,
                wraplength=440,
                justify="left",
            ).pack(anchor="w", padx=16, pady=(0, 6))

    section(tab_dictee, ">> Raccourci", "Cliquez Capturer, puis appuyez sur une touche ou un bouton souris.")

    hk_row = tk.Frame(tab_dictee, bg=C_BG)
    hk_row.pack(fill="x", padx=16)
    hk_display = tk.Label(
        hk_row,
        textvariable=hk_display_var,
        bg=C_INPUT_BG,
        fg=C_INPUT_FG,
        font=FONT_UI,
        relief="flat",
        anchor="w",
        padx=10,
        pady=6,
        takefocus=1,
        highlightthickness=1,
        highlightbackground=C_INPUT_BG,
        highlightcolor=C_ACCENT,
    )
    hk_display.pack(side="left", fill="x", expand=True, padx=(0, 8))
    capture_btn = tk.Button(
        hk_row,
        text="[ CAPTURER ]",
        bg=C_CARD_BORDER,
        fg="white",
        font=FONT_UI_SMALL,
        relief="flat",
        padx=10,
        pady=4,
    )
    capture_btn.pack(side="right")

    section(tab_dictee, ">> Langue")
    lang_codes = sorted(VALID_LANGUAGES, key=lambda c: LANGUAGE_LABELS.get(c, c))
    lang_labels = [LANGUAGE_LABELS.get(c, c) for c in lang_codes]
    lang_var = tk.StringVar(root)
    current_lang = app.config.get("language") or "fr"
    lang_var.set(LANGUAGE_LABELS.get(current_lang, current_lang))

    def _lang_from_label(label):
        for code, lbl in LANGUAGE_LABELS.items():
            if lbl == label:
                return code
        return "fr"

    lang_combo = ttk.Combobox(tab_dictee, textvariable=lang_var, values=lang_labels, font=FONT_UI, state="readonly")
    lang_combo.pack(padx=16, anchor="w")

    section(
        tab_dictee,
        ">> Profil",
        "Choisis entre vitesse et justesse. Le modèle n'est pas rechargé.",
    )
    profile_var = tk.StringVar(root, value=app.config.get("transcription_profile") or "fast")
    profile_row = tk.Frame(tab_dictee, bg=C_BG)
    profile_row.pack(fill="x", padx=12, pady=4)

    def _select_profile(key):
        profile_var.set(key)

    profile_cards = {}
    for key in ("fast", "balanced", "accurate"):
        title, subtitle = PROFILE_CARD_COPY[key]
        card = tk.Frame(profile_row, bg=C_BG, highlightthickness=2, highlightbackground=C_CARD_BORDER)
        card.pack(side="left", fill="both", expand=True, padx=4, ipady=8)

        def _mk_handler(k):
            return lambda e=None: _select_profile(k)

        card.bind("<Button-1>", _mk_handler(key))
        tk.Label(card, text=title, bg=C_BG, fg=C_TEXT, font=FONT_UI_BOLD).pack(pady=(8, 2))
        tk.Label(card, text=subtitle, bg=C_BG, fg=C_MUTED, font=FONT_UI_SMALL, wraplength=120).pack(
            pady=(0, 8)
        )
        profile_cards[key] = card

    def _refresh_profile_cards(*_):
        sel = profile_var.get()
        for key, card in profile_cards.items():
            color = C_CARD_SELECTED if key == sel else C_CARD_BORDER
            card.config(highlightbackground=color)

    profile_var.trace_add("write", _refresh_profile_cards)
    _refresh_profile_cards()

    section(
        tab_dictee,
        ">> Pré-buffer",
        "Garde en mémoire vive ce que tu dis juste avant F8… Rien n'est écrit sur le disque.",
    )
    pre_ms_init = clamp_pre_buffer_ms(app.config.get("pre_buffer_ms"))
    pre_sec_var = tk.DoubleVar(root, value=pre_ms_init / 1000.0)
    pre_label_var = tk.StringVar(root)

    def _format_pre_label(val_s):
        if val_s <= 0.05:
            return "off"
        return f"{val_s:.1f}".replace(".", ",") + " s"

    pre_label_var.set(_format_pre_label(pre_sec_var.get()))
    pre_slider_row = tk.Frame(tab_dictee, bg=C_BG)
    pre_slider_row.pack(fill="x", padx=16)
    tk.Label(pre_slider_row, text="off", bg=C_BG, fg=C_MUTED, font=FONT_UI_SMALL).pack(side="left")
    pre_scale = tk.Scale(
        pre_slider_row,
        from_=0,
        to=3,
        resolution=0.5,
        orient="horizontal",
        variable=pre_sec_var,
        bg=C_BG,
        fg=C_TEXT,
        highlightthickness=0,
        troughcolor=C_INPUT_BG,
        activebackground=C_ACCENT,
        showvalue=0,
        length=280,
    )
    pre_scale.pack(side="left", padx=8)
    tk.Label(pre_slider_row, text="3 s", bg=C_BG, fg=C_MUTED, font=FONT_UI_SMALL).pack(side="left")
    tk.Label(
        pre_slider_row,
        textvariable=pre_label_var,
        bg=C_BG,
        fg=C_INPUT_FG,
        font=FONT_MONO,
        width=8,
    ).pack(side="right")

    def _on_pre_slider(*_):
        pre_label_var.set(_format_pre_label(pre_sec_var.get()))

    pre_sec_var.trace_add("write", _on_pre_slider)

    section(tab_dictee, ">> Durée max")
    max_record_var = tk.StringVar(root, value=str(app.config.get("max_record_seconds") or 25))
    max_row = tk.Frame(tab_dictee, bg=C_BG)
    max_row.pack(fill="x", padx=16)
    tk.Entry(
        max_row,
        textvariable=max_record_var,
        width=8,
        bg=C_INPUT_BG,
        fg=C_INPUT_FG,
        font=FONT_MONO,
        relief="flat",
    ).pack(side="left")
    max_hint_var = tk.StringVar(root)

    def _refresh_max_hint(*_):
        try:
            mx = int(max_record_var.get())
        except Exception:
            mx = int(DEFAULT_CONFIG["max_record_seconds"])
        pb = int(round(float(pre_sec_var.get()) * 1000))
        max_hint_var.set(
            f"Arrêt automatique (0 = sans limite). Avec le pré-buffer, l'audio peut atteindre {mx + int(pb / 1000)} s."
        )

    max_record_var.trace_add("write", _refresh_max_hint)
    pre_sec_var.trace_add("write", _refresh_max_hint)
    _refresh_max_hint()
    tk.Label(
        tab_dictee,
        textvariable=max_hint_var,
        bg=C_BG,
        fg=C_MUTED,
        font=FONT_UI_SMALL,
        wraplength=440,
        justify="left",
    ).pack(anchor="w", padx=16, pady=(4, 0))

    # --- Micro tab ---
    section(tab_micro, ">> Périphérique d'entrée", "Liste des micros vus par PyAudio.")
    devices = enumerate_input_devices(app.recorder.audio)
    device_names = [d.name for d in devices]
    stored_device = app.config.get("input_device") or ""
    mic_var = tk.StringVar(root)
    if stored_device and stored_device in device_names:
        mic_var.set(stored_device)
    elif device_names:
        mic_var.set(device_names[0])
    else:
        mic_var.set("")

    mic_combo = ttk.Combobox(tab_micro, textvariable=mic_var, values=device_names, font=FONT_UI, state="readonly")
    mic_combo.pack(padx=16, anchor="w", fill="x")

    section(tab_micro, ">> Niveau en direct")
    vu_canvas = tk.Canvas(tab_micro, height=28, bg=C_INPUT_BG, highlightthickness=0, width=400)
    vu_canvas.pack(padx=16, pady=8, anchor="w")
    vu_after = {"id": None}

    def _vu_tick():
        if not root.winfo_exists():
            return
        vu_canvas.delete("all")
        w = max(80, vu_canvas.winfo_width())
        h = max(10, vu_canvas.winfo_height())
        level = scale_vu_level(app.recorder.get_audio_level())
        bh = vu_bar_height(level, h)
        vu_canvas.create_rectangle(0, h - bh, w, h, fill=C_ACCENT, outline="")
        vu_after["id"] = root.after(60, _vu_tick)

    _vu_tick()

    # --- Moteur tab ---
    section(tab_moteur, ">> Modèle", "Rechargé à l'enregistrement si la taille ou le dossier change.")
    model_var = tk.StringVar(root, value=app.config.get("model_size"))
    ttk.Combobox(
        tab_moteur,
        textvariable=model_var,
        values=["tiny", "base", "small", "medium", "large-v3"],
        font=FONT_UI,
    ).pack(padx=16, anchor="w")

    section(tab_moteur, ">> Unité de calcul")
    device_var = tk.StringVar(root, value=app.config.get("device"))
    ttk.Combobox(tab_moteur, textvariable=device_var, values=["auto", "cpu", "cuda"], font=FONT_UI).pack(
        padx=16, anchor="w"
    )
    if app.has_nvidia:
        tk.Label(
            tab_moteur,
            text=">> Carte NVIDIA détectée : la transcription peut utiliser CUDA.",
            bg=C_BG,
            fg=C_ACCENT,
            font=FONT_UI_SMALL,
            wraplength=440,
            justify="left",
        ).pack(anchor="w", padx=16, pady=(8, 0))

    section(tab_moteur, ">> Précision")
    compute_var = tk.StringVar(root, value=app.config.get("compute_type") or "int8")
    ttk.Combobox(
        tab_moteur,
        textvariable=compute_var,
        values=["int8", "int8_float16", "float16", "float32"],
        font=FONT_UI,
    ).pack(padx=16, anchor="w")

    dev_label = resolve_device_label(device_var.get(), app.has_nvidia)
    tk.Label(
        tab_moteur,
        text=f"Résolution actuelle : {dev_label}",
        bg=C_BG,
        fg=C_MUTED,
        font=FONT_UI_SMALL,
    ).pack(anchor="w", padx=16, pady=(12, 0))

    # --- Système tab ---
    section(
        tab_systeme,
        ">> Mises à jour",
        "Recherche facultative sur GitHub Releases. Aucun texte dicté n'est envoyé.",
    )
    check_updates_var = tk.BooleanVar(root, value=bool(app.config.get("check_updates")))

    def _toggle_check_updates():
        app.config.set("check_updates", bool(check_updates_var.get()))

    tk.Checkbutton(
        tab_systeme,
        text="Vérifier automatiquement au démarrage",
        variable=check_updates_var,
        command=_toggle_check_updates,
        bg=C_BG,
        fg=C_TEXT,
        selectcolor=C_INPUT_BG,
        activebackground=C_BG,
        font=FONT_UI_SMALL,
    ).pack(anchor="w", padx=16)
    tk.Button(
        tab_systeme,
        text="[ VÉRIFIER LES MISES À JOUR ]",
        command=app.manual_update_check,
        bg=C_CARD_BORDER,
        fg="white",
        font=FONT_UI_SMALL,
        relief="flat",
    ).pack(anchor="w", padx=16, pady=8)

    section(tab_systeme, ">> SHA256 de cet exécutable")
    sha_var = tk.StringVar(root, value="")
    sha_hint = tk.StringVar(root, value="")
    sha_row = tk.Frame(tab_systeme, bg=C_BG)
    sha_row.pack(fill="x", padx=16)
    sha_entry = tk.Entry(
        sha_row,
        textvariable=sha_var,
        bg=C_INPUT_BG,
        fg=C_INPUT_FG,
        font=FONT_MONO_SMALL,
        relief="flat",
        readonlybackground=C_INPUT_BG,
    )
    sha_entry.configure(state="readonly")
    sha_entry.pack(side="left", fill="x", expand=True)

    def _copy_sha():
        app.copy_settings_sha(sha_var, sha_hint)

    tk.Button(sha_row, text="Copier", command=_copy_sha, bg=C_CARD_BORDER, fg="white", relief="flat").pack(
        side="left", padx=6
    )
    tk.Label(tab_systeme, textvariable=sha_hint, bg=C_BG, fg=C_MUTED, font=FONT_UI_SMALL, wraplength=440).pack(
        anchor="w", padx=16
    )
    app.kickoff_local_exe_hash(sha_var, sha_hint)

    section(
        tab_systeme,
        ">> Dossier des modèles",
        "Vide = dossier « models » à côté de l'application.",
    )
    path_var = tk.StringVar(root, value=app.config.get_models_dir())

    def _browse_models():
        initial = path_var.get().strip() or app.config.get_models_dir()
        chosen = filedialog.askdirectory(
            parent=root,
            title="Dossier des modèles Whisper",
            initialdir=initial if os.path.isdir(initial) else app.app_dir,
        )
        if chosen:
            path_var.set(os.path.normpath(chosen))

    models_row = tk.Frame(tab_systeme, bg=C_BG)
    models_row.pack(fill="x", padx=16)
    tk.Entry(
        models_row,
        textvariable=path_var,
        bg=C_INPUT_BG,
        fg=C_INPUT_FG,
        font=FONT_UI,
        relief="flat",
    ).pack(side="left", fill="x", expand=True)
    tk.Button(models_row, text="…", command=_browse_models, bg=C_INPUT_BG, fg=C_ACCENT, relief="flat", width=3).pack(
        side="left", padx=4
    )

    beeps_var = tk.BooleanVar(root, value=bool(app.config.get("beeps")))
    tk.Checkbutton(
        tab_systeme,
        text="Bips au début et à la fin de dictée",
        variable=beeps_var,
        bg=C_BG,
        fg=C_TEXT,
        selectcolor=C_INPUT_BG,
        font=FONT_UI_SMALL,
    ).pack(anchor="w", padx=16, pady=(12, 0))

    log_timings_var = tk.BooleanVar(root, value=bool(app.config.get("log_pipeline_timings")))
    tk.Checkbutton(
        tab_systeme,
        text="Journaliser les durées du pipeline (débogage)",
        variable=log_timings_var,
        bg=C_BG,
        fg=C_TEXT,
        selectcolor=C_INPUT_BG,
        font=FONT_UI_SMALL,
    ).pack(anchor="w", padx=16, pady=(4, 0))

    # --- Hotkey capture ---
    def _set_hotkey_value(value):
        canon = normalize_hotkey(value)
        hk_var.set(canon)
        hk_display_var.set(display_hotkey(canon))

    def _unbind_tk_capture():
        try:
            root.unbind("<KeyPress>")
            hk_display.unbind("<KeyPress>")
        except Exception:
            pass

    def _capture_status(msg):
        try:
            if root.winfo_exists():
                hk_status_var.set(msg or "")
        except tk.TclError:
            pass

    def _capture_done(value):
        try:
            if not root.winfo_exists():
                return
            _unbind_tk_capture()
            capture_btn.config(state="normal", text="[ CAPTURER ]", bg=C_CARD_BORDER)
            hk_display.config(highlightbackground=C_INPUT_BG)
            if value:
                _set_hotkey_value(value)
                hk_status_var.set(f"Raccourci détecté : {display_hotkey(value)}")
            elif not hk_status_var.get() or "écoute" in (hk_status_var.get() or "").lower():
                hk_status_var.set("Capture annulée.")
        except tk.TclError:
            pass

    app.hotkey_capture_ui = {"on_status": _capture_status, "on_result": _capture_done}

    def _start_capture():
        if app.hotkey_capture:
            app.cancel_hotkey_capture()
            return
        capture_btn.config(text="[ ANNULER ]", bg=C_WARN)
        hk_status_var.set("Préparation de la capture…")
        hk_display.config(highlightbackground=C_ACCENT)
        root.bind("<KeyPress>", app.handle_tk_capture_keypress)
        hk_display.bind("<KeyPress>", app.handle_tk_capture_keypress)
        if not app.start_hotkey_capture():
            _unbind_tk_capture()
            capture_btn.config(text="[ CAPTURER ]", bg=C_CARD_BORDER)
            hk_status_var.set("Capture impossible.")

    capture_btn.config(command=_start_capture)

    def _on_close():
        if vu_after["id"]:
            try:
                root.after_cancel(vu_after["id"])
            except Exception:
                pass
        app.hotkey_capture_ui = None
        app.stop_hotkey_capture(join=True)
        app.setup_hotkey()
        try:
            root.destroy()
        except Exception:
            pass

    root.protocol("WM_DELETE_WINDOW", _on_close)

    # --- Footer ---
    footer = tk.Frame(outer, bg=C_BG)
    footer.pack(fill="x", side="bottom", padx=16, pady=(8, 12))
    tk.Label(
        footer,
        text="Les modifications s'appliquent à l'enregistrement.",
        bg=C_BG,
        fg=C_MUTED,
        font=FONT_UI_SMALL,
    ).pack(side="left")

    def _test_dictation():
        app.queue.put("toggle_recording")

    tk.Button(
        footer,
        text="[ TESTER LA DICTÉE ]",
        command=_test_dictation,
        bg=C_CARD_BORDER,
        fg="white",
        font=FONT_UI_SMALL,
        relief="flat",
    ).pack(side="left", padx=(16, 0))

    def save():
        try:
            max_record = int(max_record_var.get())
        except Exception:
            max_record = DEFAULT_CONFIG["max_record_seconds"]
        pre_buffer_ms = clamp_pre_buffer_ms(int(round(float(pre_sec_var.get()) * 1000)))
        old_model = app.config.get("model_size")
        old_device = app.config.get("device")
        old_compute = app.config.get("compute_type")
        old_models_resolved = app.config.get_models_dir()
        old_input = app.config.get("input_device") or ""

        new_models_input = path_var.get().strip()
        new_models_resolved = resolve_models_dir(app.app_dir, new_models_input if new_models_input else None)
        models_cfg = canonical_models_dir_config(new_models_resolved, app.app_dir)

        if (
            os.path.normcase(new_models_resolved) != os.path.normcase(old_models_resolved)
            and directory_has_model_files(old_models_resolved)
        ):
            choice = messagebox.askyesnocancel(
                "CyberScribe — modèles",
                "Le dossier des modèles change.\n\n"
                "Déplacer les fichiers existants vers le nouveau dossier ?\n\n"
                "Oui = déplacer\nNon = copier\nAnnuler = garder l'ancien dossier",
                parent=root,
            )
            if choice is None:
                return
            ok, migrate_msg = migrate_models_directory(
                old_models_resolved, new_models_resolved, move=bool(choice)
            )
            if not ok:
                messagebox.showerror("CyberScribe", f"Migration impossible :\n{migrate_msg}", parent=root)
                return
            app.log_message(migrate_msg)
        else:
            try:
                ensure_models_dir(new_models_resolved)
            except OSError as e:
                messagebox.showerror("CyberScribe", f"Dossier des modèles inaccessible :\n{e}", parent=root)
                return

        app.stop_hotkey_capture(join=True)
        app.hotkey_capture_ui = None
        selected_mic = mic_var.get().strip()
        if selected_mic not in device_names:
            selected_mic = ""

        app.config.update(
            {
                "hotkey": normalize_hotkey(hk_var.get()),
                "language": _lang_from_label(lang_var.get()),
                "model_size": model_var.get(),
                "device": device_var.get(),
                "compute_type": compute_var.get(),
                "transcription_profile": profile_var.get() or "fast",
                "max_record_seconds": max_record,
                "pre_buffer_ms": pre_buffer_ms,
                "models_dir": models_cfg,
                "beeps": bool(beeps_var.get()),
                "log_pipeline_timings": bool(log_timings_var.get()),
                "input_device": selected_mic,
            }
        )
        app.recorder.set_pre_buffer_ms(pre_buffer_ms)
        app.recorder.set_input_device(selected_mic)
        if (selected_mic or "") != (old_input or ""):
            app.recorder.restart_input_monitor()
        else:
            app.recorder.start_background_capture()

        if not app.setup_hotkey():
            messagebox.showwarning("CyberScribe", "Raccourci invalide. Retour à F8.", parent=root)
            _set_hotkey_value("F8")

        models_changed = os.path.normcase(app.config.get_models_dir()) != os.path.normcase(old_models_resolved)
        model_changed = (
            app.config.get("model_size") != old_model
            or app.config.get("device") != old_device
            or app.config.get("compute_type") != old_compute
            or models_changed
        )
        if model_changed:
            app.transcriber.reload()
            app.update_tray_icon(state="loading")
            messagebox.showinfo(
                "CyberScribe",
                "Configuration enregistrée.\nLe modèle se recharge en arrière-plan.",
                parent=root,
            )
        else:
            messagebox.showinfo("CyberScribe", "Configuration enregistrée.", parent=root)
        _on_close()
        app.sync_tray_menu()

    tk.Button(
        footer,
        text=">> ENREGISTRER <<",
        command=save,
        bg=C_ACCENT,
        fg="#0f172a",
        font=FONT_UI_BOLD,
        relief="flat",
        padx=16,
        pady=6,
    ).pack(side="right")