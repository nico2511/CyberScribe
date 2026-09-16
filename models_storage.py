"""Resolve and migrate on-disk Whisper model directories."""

from __future__ import annotations

import logging
import os
import shutil
from typing import Optional, Tuple

MODELS_FOLDER_NAME = "models"


def default_models_dir(app_dir: str) -> str:
    return os.path.normpath(os.path.join(app_dir, MODELS_FOLDER_NAME))


def resolve_models_dir(app_dir: str, models_dir_config: Optional[str]) -> str:
    """Turn config value (empty, relative, env vars) into an absolute directory path."""
    raw = (models_dir_config or "").strip()
    if not raw:
        path = default_models_dir(app_dir)
    else:
        path = os.path.expandvars(os.path.expanduser(raw))
        if not os.path.isabs(path):
            path = os.path.join(app_dir, path)
        path = os.path.normpath(path)
    return path


def canonical_models_dir_config(resolved_path: str, app_dir: str) -> str:
    """Prefer portable values in config.json (%LOCALAPPDATA%… or empty for default)."""
    resolved_path = os.path.normpath(resolved_path)
    if os.path.normcase(resolved_path) == os.path.normcase(default_models_dir(app_dir)):
        return ""

    local = os.environ.get("LOCALAPPDATA", "")
    if local:
        local_norm = os.path.normcase(os.path.normpath(local))
        if os.path.normcase(resolved_path).startswith(local_norm):
            suffix = resolved_path[len(local) :]
            if suffix.startswith("\\") or suffix.startswith("/"):
                suffix = suffix[1:]
            return "%LOCALAPPDATA%\\" + suffix.replace("/", "\\")

    return resolved_path


def ensure_models_dir(path: str) -> str:
    os.makedirs(path, exist_ok=True)
    return path


def directory_has_model_files(path: str) -> bool:
    if not path or not os.path.isdir(path):
        return False
    for root, _dirs, files in os.walk(path):
        if files:
            return True
    return False


def _same_path(a: str, b: str) -> bool:
    try:
        return os.path.normcase(os.path.normpath(a)) == os.path.normcase(os.path.normpath(b))
    except Exception:
        return False


def migrate_models_directory(
    source_dir: str,
    dest_dir: str,
    move: bool = True,
) -> Tuple[bool, str]:
    """
    Copy or move Whisper model files from source_dir into dest_dir.
    Returns (success, human-readable message).
    """
    source_dir = os.path.normpath(source_dir)
    dest_dir = os.path.normpath(dest_dir)

    if _same_path(source_dir, dest_dir):
        return True, "Le dossier des modèles est inchangé."

    if not os.path.isdir(source_dir):
        ensure_models_dir(dest_dir)
        return True, "Aucun modèle à déplacer (ancien dossier absent)."

    if not directory_has_model_files(source_dir):
        ensure_models_dir(dest_dir)
        return True, "Ancien dossier vide — nouveau dossier prêt."

    ensure_models_dir(dest_dir)

    try:
        for entry in os.listdir(source_dir):
            src = os.path.join(source_dir, entry)
            dst = os.path.join(dest_dir, entry)
            if os.path.isdir(src):
                if os.path.exists(dst):
                    shutil.copytree(src, dst, dirs_exist_ok=True)
                    if move:
                        shutil.rmtree(src, ignore_errors=True)
                else:
                    if move:
                        shutil.move(src, dst)
                    else:
                        shutil.copytree(src, dst)
            else:
                if os.path.exists(dst):
                    if move:
                        os.remove(dst)
                    else:
                        continue
                if move:
                    shutil.move(src, dst)
                else:
                    shutil.copy2(src, dst)

        if move:
            try:
                remaining = os.listdir(source_dir)
                if not remaining:
                    os.rmdir(source_dir)
            except OSError:
                pass
    except Exception as e:
        logging.exception("Model migration failed")
        return False, str(e)

    action = "déplacés" if move else "copiés"
    return True, f"Modèles {action} vers le nouveau dossier."
