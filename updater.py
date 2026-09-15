"""
CyberScribe — in-place updater for the PyInstaller Windows executable.

Design constraints (Windows):
- A running .exe cannot overwrite itself; we download CyberScribe.update.exe beside the
  live binary and hand off to a short-lived .cmd that waits for exit, swaps files, restarts.
- Updates apply only when sys.frozen is True (shipped build). Dev runs can still query GitHub.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Callable, Optional

GITHUB_REPO = "nico2511/CyberScribe"
RELEASES_LATEST_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
EXE_ASSET_NAME = "CyberScribe.exe"
SHA256_ASSET_SUFFIX = ".sha256"
UPDATE_STAGING_NAME = "CyberScribe.update.exe"
APPLY_SCRIPT_NAME = "_cyberscribe_apply_update.cmd"
MIN_EXE_BYTES = 5 * 1024 * 1024  # sanity floor (~5 MB); real binary is much larger

_VERSION_RE = re.compile(r"^v?(?P<parts>\d+(?:\.\d+)*)", re.IGNORECASE)


@dataclass(frozen=True)
class ReleaseInfo:
    version: str
    tag: str
    exe_url: str
    exe_size: Optional[int]
    sha256_url: Optional[str]
    release_page: str
    notes: str


@dataclass
class UpdateCheckResult:
    ok: bool
    current_version: str
    latest: Optional[ReleaseInfo] = None
    update_available: bool = False
    error: Optional[str] = None


def parse_version(version: str) -> tuple[int, ...]:
    """Parse '1.2.0' or 'v1.2.0' into a comparable tuple."""
    if not version:
        return (0,)
    match = _VERSION_RE.match(version.strip())
    if not match:
        return (0,)
    parts = match.group("parts").split(".")
    out = []
    for part in parts:
        try:
            out.append(int(part))
        except ValueError:
            break
    return tuple(out) if out else (0,)


def version_less(a: str, b: str) -> bool:
    return parse_version(a) < parse_version(b)


def is_frozen_build() -> bool:
    return bool(getattr(sys, "frozen", False))


def _user_agent(app_version: str) -> str:
    return f"CyberScribe/{app_version} (Windows updater)"


def _api_request(url: str, app_version: str, timeout: float = 20.0) -> bytes:
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": _user_agent(app_version),
        },
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def _normalize_tag(tag_name: str) -> str:
    tag = (tag_name or "").strip()
    if tag.lower().startswith("v"):
        return tag[1:]
    return tag


def _pick_asset(assets: list, name: str) -> Optional[dict]:
    for asset in assets or []:
        if asset.get("name") == name:
            return asset
    return None


def fetch_latest_release(app_version: str) -> ReleaseInfo:
    raw = _api_request(RELEASES_LATEST_URL, app_version)
    data = json.loads(raw.decode("utf-8"))
    assets = data.get("assets") or []
    exe_asset = _pick_asset(assets, EXE_ASSET_NAME)
    if not exe_asset or not exe_asset.get("browser_download_url"):
        raise ValueError(f"No {EXE_ASSET_NAME} asset on latest GitHub release.")

    sha_name = EXE_ASSET_NAME + SHA256_ASSET_SUFFIX
    sha_asset = _pick_asset(assets, sha_name)

    tag = data.get("tag_name") or ""
    version = _normalize_tag(tag)
    return ReleaseInfo(
        version=version,
        tag=tag,
        exe_url=exe_asset["browser_download_url"],
        exe_size=exe_asset.get("size"),
        sha256_url=sha_asset.get("browser_download_url") if sha_asset else None,
        release_page=data.get("html_url") or f"https://github.com/{GITHUB_REPO}/releases/latest",
        notes=(data.get("body") or "").strip(),
    )


def check_for_update(current_version: str) -> UpdateCheckResult:
    try:
        latest = fetch_latest_release(current_version)
        available = version_less(current_version, latest.version)
        return UpdateCheckResult(
            ok=True,
            current_version=current_version,
            latest=latest,
            update_available=available,
        )
    except urllib.error.HTTPError as e:
        return UpdateCheckResult(
            ok=False,
            current_version=current_version,
            error=f"GitHub API HTTP {e.code}",
        )
    except urllib.error.URLError as e:
        return UpdateCheckResult(
            ok=False,
            current_version=current_version,
            error=f"Network error: {e.reason}",
        )
    except Exception as e:
        logging.exception("Update check failed")
        return UpdateCheckResult(
            ok=False,
            current_version=current_version,
            error=str(e),
        )


def _download_file(
    url: str,
    dest_path: str,
    app_version: str,
    progress: Optional[Callable[[int, Optional[int]], None]] = None,
    timeout: float = 300.0,
) -> None:
    req = urllib.request.Request(url, headers={"User-Agent": _user_agent(app_version)}, method="GET")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        total = resp.headers.get("Content-Length")
        total_int = int(total) if total and total.isdigit() else None
        read = 0
        chunk_size = 256 * 1024
        with open(dest_path, "wb") as out:
            while True:
                chunk = resp.read(chunk_size)
                if not chunk:
                    break
                out.write(chunk)
                read += len(chunk)
                if progress:
                    progress(read, total_int)


def _fetch_expected_sha256(url: str, app_version: str) -> Optional[str]:
    try:
        raw = _api_request(url, app_version, timeout=30.0)
        text = raw.decode("utf-8", errors="replace").strip()
        # Accept bare hex or "HASH  filename" (certutil-style)
        token = text.split()[0].strip().lower()
        if re.fullmatch(r"[a-f0-9]{64}", token):
            return token
    except Exception:
        logging.warning("Could not fetch SHA256 sidecar from release")
    return None


def _file_sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def download_release_exe(
    release: ReleaseInfo,
    app_dir: str,
    app_version: str,
    progress: Optional[Callable[[int, Optional[int]], None]] = None,
) -> str:
    """Download the release EXE to CyberScribe.update.exe in app_dir. Returns path."""
    os.makedirs(app_dir, exist_ok=True)
    dest = os.path.join(app_dir, UPDATE_STAGING_NAME)
    tmp_fd, tmp_path = tempfile.mkstemp(prefix="cyberscribe_dl_", suffix=".exe", dir=app_dir)
    os.close(tmp_fd)
    try:
        _download_file(release.exe_url, tmp_path, app_version, progress=progress)
        size = os.path.getsize(tmp_path)
        if size < MIN_EXE_BYTES:
            raise ValueError(f"Downloaded file too small ({size} bytes); aborting.")

        if release.sha256_url:
            expected = _fetch_expected_sha256(release.sha256_url, app_version)
            if expected:
                actual = _file_sha256(tmp_path)
                if actual.lower() != expected.lower():
                    raise ValueError("SHA256 mismatch for downloaded executable.")

        if os.path.exists(dest):
            try:
                os.remove(dest)
            except OSError:
                pass
        os.replace(tmp_path, dest)
        return dest
    except Exception:
        try:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
        except OSError:
            pass
        raise


def write_apply_script(app_dir: str, exe_name: str) -> str:
    """Create a cmd script that waits for the app to exit, swaps EXE, restarts, self-deletes."""
    script_path = os.path.join(app_dir, APPLY_SCRIPT_NAME)
    staging = UPDATE_STAGING_NAME
    lines = [
        "@echo off",
        "setlocal",
        f'set "DIR=%~dp0"',
        f'set "LIVE=%DIR%{exe_name}"',
        f'set "NEW=%DIR%{staging}"',
        f'set "OLD=%DIR%{exe_name}.bak"',
        'if not exist "%NEW%" exit /b 1',
        ":wait",
        f'tasklist /FI "IMAGENAME eq {exe_name}" 2>nul | find /I "{exe_name}" >nul',
        "if %ERRORLEVEL%==0 (",
        "  timeout /t 1 /nobreak >nul",
        "  goto wait",
        ")",
        'if exist "%OLD%" del /f /q "%OLD%"',
        'if exist "%LIVE%" move /y "%LIVE%" "%OLD%"',
        'move /y "%NEW%" "%LIVE%"',
        'start "" "%LIVE%"',
        'del /f /q "%~f0"',
        "endlocal",
    ]
    with open(script_path, "w", encoding="utf-8", newline="\r\n") as f:
        f.write("\r\n".join(lines) + "\r\n")
    return script_path


def launch_apply_and_exit(app_dir: str, exe_name: str) -> None:
    script = write_apply_script(app_dir, exe_name)
    flags = 0
    if sys.platform == "win32":
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(
            subprocess, "DETACHED_PROCESS", 0
        )
    subprocess.Popen(
        ["cmd.exe", "/c", script],
        cwd=app_dir,
        creationflags=flags,
        close_fds=True,
    )


def cleanup_staging(app_dir: str, remove_partial_download: bool = False) -> None:
    """Remove leftover apply script; optionally drop an unfinished staging EXE."""
    names = [APPLY_SCRIPT_NAME]
    if remove_partial_download:
        names.insert(0, UPDATE_STAGING_NAME)
    for name in names:
        path = os.path.join(app_dir, name)
        try:
            if os.path.exists(path):
                os.remove(path)
        except OSError:
            pass
