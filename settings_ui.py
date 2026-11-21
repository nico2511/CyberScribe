"""Configuration window (4 tabs, French UI). Does not import CyberScribe."""

from __future__ import annotations

import os
import tkinter as tk
from tkinter import filedialog, messagebox

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
    C_INPUT_BG,
    C_INPUT_FG,
    C_MUTED,
    C_TEXT,
    C_WARN,
    CONFIG_WINDOW_HEIGHT,
    CONFIG_WINDOW_WIDTH,
    CONTENT_PADX,
    FONT_MONO,
    FONT_MONO_SMALL,
    FONT_UI,
    FONT_UI_SMALL,
    LANGUAGE_LABELS,
)
from ui_widgets import (
    DarkDropdown,
    PreBufferCanvas,
    TabStrip,
    build_profile_cards,
    config_footer,
    config_shell,
    dark_entry,
    muted_rule,
    outline_button,
    section_header,
)


def _header_status(app) -> str:
    states = {
        "ready": "prêt",
        "loading": "chargement",
        "recording": "écoute",
        "transcribing": "transcription",
    }
    mode = states.get(getattr(app, "_tray_mode", "ready"), "prêt")
    model = str(app.config.get("model_size") or "base")
    dev = resolve_device_label(str(app.config.get("device") or "auto"), app.has_nvidia)
    return f"● {mode} · {model} · {dev}"


def open_settings_window(app):
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
    ws, hs = root.winfo_screenwidth(), root.winfo_screenheight()
    x = (ws - CONFIG_WINDOW_WIDTH) // 2
    y = max(16, (hs - CONFIG_WINDOW_HEIGHT) // 2)
    root.geometry(f"{CONFIG_WINDOW_WIDTH}x{CONFIG_WINDOW_HEIGHT}+{x}+{y}")
    root.minsize(CONFIG_WINDOW_WIDTH, 520)
    root.resizable(True, True)
    root.attributes("-topmost", True)
    root.after(100, lambda: root.attributes("-topmost", False))

    outer, host = config_shell(root, "/// Configuration", _header_status(app))
    tab_dictee = tk.Frame(host, bg=C_BG)
    tab_micro = tk.Frame(host, bg=C_BG)
    tab_moteur = tk.Frame(host, bg=C_BG)
    tab_systeme = tk.Frame(host, bg=C_BG)
    frames = {"Dictée": tab_dictee, "Micro": tab_micro, "Moteur": tab_moteur, "Système": tab_systeme}
    TabStrip(host, list(frames.keys()), frames)

    hk_var = tk.StringVar(root, value=normalize_hotkey(app.config.get("hotkey")))
    hk_display_var = tk.StringVar(root, value=display_hotkey(hk_var.get()))
    hk_status_var = tk.StringVar(root, value="")

    # --- Dictée ---
    row_hk_lang = tk.Frame(tab_dictee, bg=C_BG)
    row_hk_lang.pack(fill="x")
    col_hk = tk.Frame(row_hk_lang, bg=C_BG)
    col_lang = tk.Frame(row_hk_lang, bg=C_BG)
    col_hk.pack(side="left", fill="both", expand=True, padx=(CONTENT_PADX, 8))
    col_lang.pack(side="left", fill="both", expand=True, padx=(8, CONTENT_PADX))

    section_header(col_hk, ">> Raccourci", "Cliquez Capturer, puis appuyez sur une touche\nou un bouton souris.")
    hk_row = tk.Frame(col_hk, bg=C_BG)
    hk_row.pack(fill="x", pady=(0, 4))
    hk_display = tk.Label(
        hk_row,
        textvariable=hk_display_var,
        bg=C_INPUT_BG,
        fg=C_INPUT_FG,
        font=FONT_MONO,
        anchor="w",
        padx=10,
        pady=8,
        highlightthickness=1,
        highlightbackground=C_CARD_BORDER,
        takefocus=1,
    )
    hk_display.pack(side="left", fill="x", expand=True, padx=(0, 6))
    capture_btn = outline_button(hk_row, "[ CAPTURER ]", lambda: _start_capture(), padx=8)
    capture_btn.pack(side="right")

    section_header(col_lang, ">> Langue")
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

    DarkDropdown(col_lang, lang_var, lang_labels).pack(fill="x")

    def _start_capture():
        if app.hotkey_capture:
            app.cancel_hotkey_capture()
            return
        capture_btn.config(text="[ ANNULER ]")
        hk_status_var.set("Préparation de la capture…")
        hk_display.config(highlightbackground=C_ACCENT)
        root.bind("<KeyPress>", app.handle_tk_capture_keypress)
        hk_display.bind("<KeyPress>", app.handle_tk_capture_keypress)
        if not app.start_hotkey_capture():
            _unbind_tk_capture()
            capture_btn.config(text="[ CAPTURER ]")
            hk_status_var.set("Capture impossible.")

    section_header(
        tab_dictee,
        ">> Profil",
        help_lines=["Choisis entre vitesse et justesse.", "Le modèle n'est pas rechargé."],
    )
    profile_var = tk.StringVar(root, value=app.config.get("transcription_profile") or "fast")
    build_profile_cards(tab_dictee, profile_var, lambda _k: None)

    section_header(
        tab_dictee,
        ">> Pré-buffer",
        help_lines=[
            "Garde en mémoire vive ce que tu dis juste avant F8,",
            "même si tu appuies un peu tard. Rien n'est écrit sur le disque.",
        ],
    )
    pre_ms_init = clamp_pre_buffer_ms(app.config.get("pre_buffer_ms"))
    pre_sec_var = tk.DoubleVar(root, value=pre_ms_init / 1000.0)
    pre_row = tk.Frame(tab_dictee, bg=C_BG)
    pre_row.pack(fill="x", padx=CONTENT_PADX)
    val_lbl = tk.Label(pre_row, text="", bg=C_BG, fg=C_INPUT_FG, font=FONT_MONO)
    val_lbl.pack(side="right", padx=(8, 0))
    pre_canvas = PreBufferCanvas(pre_row, pre_sec_var)
    pre_canvas.pack(side="left", fill="x", expand=True)
    pre_canvas.attach_value_label(val_lbl)
    pre_canvas._draw()

    section_header(tab_dictee, ">> Durée max")
    max_record_var = tk.StringVar(root, value=f"{app.config.get('max_record_seconds') or 25} s")
    dur_row = tk.Frame(tab_dictee, bg=C_BG)
    dur_row.pack(fill="x", padx=CONTENT_PADX, pady=(4, 0))
    dark_entry(dur_row, max_record_var, width=7).pack(side="left")
    hint_col = tk.Frame(dur_row, bg=C_BG)
    hint_col.pack(side="left", padx=(12, 0))
    hint_line1 = tk.Label(
        hint_col,
        text="Arrêt automatique (0 = sans limite).",
        bg=C_BG,
        fg=C_MUTED,
        font=FONT_UI_SMALL,
        anchor="w",
    )
    hint_line1.pack(anchor="w")
    hint_line2 = tk.Frame(hint_col, bg=C_BG)
    hint_line2.pack(anchor="w")
    hint_pre = tk.Label(hint_line2, text="Avec le pré-buffer, l'audio peut atteindre ", bg=C_BG, fg=C_MUTED, font=FONT_UI_SMALL)
    hint_pre.pack(side="left")
    hint_val = tk.Label(hint_line2, text="26 s", bg=C_BG, fg=C_ACCENT, font=FONT_MONO)
    hint_val.pack(side="left")
    hint_dot = tk.Label(hint_line2, text=".", bg=C_BG, fg=C_MUTED, font=FONT_UI_SMALL)
    hint_dot.pack(side="left")

    def _refresh_max_hint(*_):
        try:
            mx = int(str(max_record_var.get()).replace("s", "").strip())
        except Exception:
            mx = int(DEFAULT_CONFIG["max_record_seconds"])
        pb = int(round(float(pre_sec_var.get()) * 1000))
        hint_val.config(text=f"{mx + int(pb / 1000)} s")

    max_record_var.trace_add("write", _refresh_max_hint)
    pre_sec_var.trace_add("write", _refresh_max_hint)
    _refresh_max_hint()

    # --- Micro ---
    section_header(tab_micro, ">> Périphérique d'entrée", "Liste des micros vus par PyAudio.")
    devices = enumerate_input_devices(app.recorder.audio)
    device_names = [d.name for d in devices]
    stored_device = app.config.get("input_device") or ""
    mic_var = tk.StringVar(root)
    if stored_device and stored_device in device_names:
        mic_var.set(stored_device)
    elif device_names:
        mic_var.set(device_names[0])
    DarkDropdown(tab_micro, mic_var, device_names or ["(aucun périphérique)"]).pack(
        fill="x", padx=CONTENT_PADX
    )

    section_header(tab_micro, ">> Niveau en direct")
    vu_canvas = tk.Canvas(tab_micro, height=36, bg=C_INPUT_BG, highlightthickness=1, highlightbackground=C_CARD_BORDER)
    vu_canvas.pack(fill="x", padx=CONTENT_PADX, pady=8)
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

    # --- Moteur ---
    section_header(tab_moteur, ">> Modèle", "Rechargé à l'enregistrement si la taille ou le dossier change.")
    model_var = tk.StringVar(root, value=app.config.get("model_size"))
    DarkDropdown(
        tab_moteur,
        model_var,
        ["tiny", "base", "small", "medium", "large-v3"],
    ).pack(fill="x", padx=CONTENT_PADX)

    section_header(tab_moteur, ">> Unité de calcul")
    device_var = tk.StringVar(root, value=app.config.get("device"))
    DarkDropdown(tab_moteur, device_var, ["auto", "cpu", "cuda"]).pack(fill="x", padx=CONTENT_PADX)
    if app.has_nvidia:
        banner = tk.Frame(tab_moteur, bg=C_INPUT_BG, highlightthickness=0)
        banner.pack(fill="x", padx=CONTENT_PADX, pady=(10, 0))
        tk.Frame(banner, bg=C_ACCENT, width=4).pack(side="left", fill="y")
        tk.Label(
            banner,
            text=">> Carte NVIDIA détectée : la transcription utilisera CUDA.",
            bg=C_INPUT_BG,
            fg=C_TEXT,
            font=FONT_UI_SMALL,
            anchor="w",
            padx=10,
            pady=8,
        ).pack(side="left", fill="x", expand=True)

    section_header(tab_moteur, ">> Précision")
    compute_var = tk.StringVar(root, value=app.config.get("compute_type") or "int8")
    DarkDropdown(
        tab_moteur,
        compute_var,
        ["int8", "int8_float16", "float16", "float32"],
    ).pack(fill="x", padx=CONTENT_PADX)

    # --- Système ---
    section_header(
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
    ).pack(anchor="w", padx=CONTENT_PADX)
    outline_button(tab_systeme, "[ VÉRIFIER LES MISES À JOUR ]", app.manual_update_check).pack(
        anchor="w", padx=CONTENT_PADX, pady=8
    )

    section_header(tab_systeme, ">> SHA256 de cet exécutable")
    sha_var = tk.StringVar(root, value="")
    sha_hint = tk.StringVar(root, value="")
    sha_row = tk.Frame(tab_systeme, bg=C_BG)
    sha_row.pack(fill="x", padx=CONTENT_PADX)
    sha_entry = tk.Entry(
        sha_row,
        textvariable=sha_var,
        bg=C_INPUT_BG,
        fg=C_INPUT_FG,
        font=FONT_MONO_SMALL,
        relief="flat",
        readonlybackground=C_INPUT_BG,
        highlightthickness=1,
        highlightbackground=C_CARD_BORDER,
    )
    sha_entry.configure(state="readonly")
    sha_entry.pack(side="left", fill="x", expand=True, ipady=4)
    outline_button(sha_row, "Copier", lambda: app.copy_settings_sha(sha_var, sha_hint), padx=8).pack(
        side="left", padx=(8, 0)
    )
    tk.Label(tab_systeme, textvariable=sha_hint, bg=C_BG, fg=C_MUTED, font=FONT_UI_SMALL, wraplength=600).pack(
        anchor="w", padx=CONTENT_PADX
    )
    app.kickoff_local_exe_hash(sha_var, sha_hint)

    section_header(tab_systeme, ">> Dossier des modèles", "Vide = dossier « models » à côté de l'application.")
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
    models_row.pack(fill="x", padx=CONTENT_PADX)
    dark_entry(models_row, path_var, width=48, mono=False).pack(side="left", fill="x", expand=True)
    outline_button(models_row, "…", _browse_models, padx=6).pack(side="left", padx=(8, 0))

    beeps_var = tk.BooleanVar(root, value=bool(app.config.get("beeps")))
    tk.Checkbutton(
        tab_systeme,
        text="Bips au début et à la fin de dictée",
        variable=beeps_var,
        bg=C_BG,
        fg=C_TEXT,
        selectcolor=C_INPUT_BG,
        font=FONT_UI_SMALL,
    ).pack(anchor="w", padx=CONTENT_PADX, pady=(12, 0))

    def _unbind_tk_capture():
        try:
            root.unbind("<KeyPress>")
            hk_display.unbind("<KeyPress>")
        except Exception:
            pass

    log_timings_var = tk.BooleanVar(root, value=bool(app.config.get("log_pipeline_timings")))
    tk.Checkbutton(
        tab_systeme,
        text="Journaliser les durées du pipeline (débogage)",
        variable=log_timings_var,
        bg=C_BG,
        fg=C_TEXT,
        selectcolor=C_INPUT_BG,
        font=FONT_UI_SMALL,
    ).pack(anchor="w", padx=CONTENT_PADX, pady=(4, 0))

    def _set_hotkey_value(value):
        canon = normalize_hotkey(value)
        hk_var.set(canon)
        hk_display_var.set(display_hotkey(canon))

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
            capture_btn.config(text="[ CAPTURER ]")
            hk_display.config(highlightbackground=C_CARD_BORDER)
            if value:
                _set_hotkey_value(value)
                hk_status_var.set(f"Raccourci détecté : {display_hotkey(value)}")
            elif not hk_status_var.get() or "écoute" in (hk_status_var.get() or "").lower():
                hk_status_var.set("Capture annulée.")
        except tk.TclError:
            pass

    app.hotkey_capture_ui = {"on_status": _capture_status, "on_result": _capture_done}

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

    def save():
        try:
            max_record = int(str(max_record_var.get()).replace("s", "").strip())
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

    config_footer(
        outer,
        on_test=lambda: app.queue.put("toggle_recording"),
        on_save=save,
    )