"""Read image bytes from the OS clipboard (macOS first; Linux/Windows best-effort)."""

from __future__ import annotations

import base64
import os
import platform
import subprocess
import tempfile
from pathlib import Path


def read_clipboard_image() -> tuple[bytes, str] | None:
    """Return ``(png_or_image_bytes, mime)`` when the clipboard holds an image.

    Prefer macOS pasteboard PNG. Returns None when no image is available or
    the platform helper fails.
    """
    system = platform.system()
    if system == "Darwin":
        return _read_macos()
    if system == "Linux":
        return _read_linux()
    if system == "Windows":
        return _read_windows()
    return None


def _read_macos() -> tuple[bytes, str] | None:
    tmp = Path(tempfile.gettempdir()) / f"sandwalk-clipboard-{os.getpid()}.png"
    try:
        proc = subprocess.run(
            [
                "osascript",
                "-e",
                'set imageData to the clipboard as "PNGf"',
                "-e",
                f'set fileRef to open for access POSIX file "{tmp}" with write permission',
                "-e",
                "set eof fileRef to 0",
                "-e",
                "write imageData to fileRef",
                "-e",
                "close access fileRef",
            ],
            capture_output=True,
            timeout=5,
            check=False,
        )
        if proc.returncode != 0 or not tmp.is_file():
            return None
        data = tmp.read_bytes()
        if not data:
            return None
        return data, "image/png"
    except (OSError, subprocess.SubprocessError, TimeoutError):
        return None
    finally:
        try:
            tmp.unlink(missing_ok=True)
        except OSError:
            pass


def _read_linux() -> tuple[bytes, str] | None:
    for cmd in (
        ["wl-paste", "-t", "image/png"],
        ["xclip", "-selection", "clipboard", "-t", "image/png", "-o"],
    ):
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                timeout=5,
                check=False,
            )
        except (OSError, subprocess.SubprocessError, TimeoutError):
            continue
        if proc.returncode == 0 and proc.stdout:
            return proc.stdout, "image/png"
    return None


def _read_windows() -> tuple[bytes, str] | None:
    script = (
        "Add-Type -AssemblyName System.Windows.Forms; "
        "$img = [System.Windows.Forms.Clipboard]::GetImage(); "
        "if ($img) { "
        "$ms = New-Object System.IO.MemoryStream; "
        "$img.Save($ms, [System.Drawing.Imaging.ImageFormat]::Png); "
        "[System.Convert]::ToBase64String($ms.ToArray()) "
        "}"
    )
    try:
        proc = subprocess.run(
            [
                "powershell.exe",
                "-NonInteractive",
                "-NoProfile",
                "-Command",
                script,
            ],
            capture_output=True,
            timeout=8,
            check=False,
            text=True,
        )
    except (OSError, subprocess.SubprocessError, TimeoutError):
        return None
    if proc.returncode != 0:
        return None
    b64 = (proc.stdout or "").strip()
    if not b64:
        return None
    try:
        return base64.b64decode(b64), "image/png"
    except (ValueError, TypeError):
        return None
