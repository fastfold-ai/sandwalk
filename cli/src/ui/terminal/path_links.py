"""Detect and open local paths / URLs from transcript text (click-to-open).

prompt_toolkit does not preserve OSC-8 hyperlinks, so Warp cannot open paths
painted inside the fullscreen TUI. We underline path-like spans and open them
on plain click via the OS handler.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import webbrowser
from pathlib import Path

# Absolute unix/mac paths, home paths, file://, and http(s) URLs.
_LINK_RE = re.compile(
    r"(?P<url>https?://[^\s\]\)\"'<>]+)"
    r"|(?P<file>file://[^\s\]\)\"'<>]+)"
    r"|(?P<path>(?:/Users|/home|~/?)[^\s\]\)\"'<>]+)"
)

# Trailing punctuation often sticks to paths in prose.
_TRAIL = ".,;:)]}'\"`"


def _strip_trail(value: str) -> str:
    text = str(value or "")
    while text and text[-1] in _TRAIL:
        text = text[:-1]
    return text


def iter_link_spans(line: str) -> list[tuple[int, int, str, str]]:
    """Return ``(start, end, kind, target)`` spans in display order.

    ``kind`` is ``url`` or ``path``. ``target`` is the openable string
    (``https://…`` or absolute filesystem path).
    """
    text = str(line or "")
    out: list[tuple[int, int, str, str]] = []
    for match in _LINK_RE.finditer(text):
        raw = _strip_trail(match.group(0))
        if not raw:
            continue
        start = match.start()
        end = start + len(raw)
        if match.group("url"):
            out.append((start, end, "url", raw))
            continue
        if match.group("file"):
            path = raw[7:] if raw.startswith("file://") else raw
            out.append((start, end, "path", path))
            continue
        path = os.path.expanduser(raw)
        out.append((start, end, "path", path))
    return out


def link_at(line: str, x: int) -> tuple[str, str] | None:
    """Return ``(kind, target)`` if column ``x`` hits a link span."""
    if x < 0:
        return None
    for start, end, kind, target in iter_link_spans(line):
        if start <= x < end:
            return kind, target
    return None


def open_link(kind: str, target: str) -> bool:
    """Open a URL or local path with the OS handler. Returns True on success."""
    if kind == "url":
        try:
            webbrowser.open(target)
            return True
        except Exception:  # noqa: BLE001
            return False

    path = Path(os.path.expanduser(target)).expanduser()
    # Only open existing files/dirs — avoid launching junk on partial clicks.
    if not path.exists():
        # Still try — some hosts resolve aliases; fail soft.
        pass
    try:
        if sys.platform == "darwin":
            subprocess.Popen(["open", str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True
        if sys.platform.startswith("linux"):
            subprocess.Popen(
                ["xdg-open", str(path)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return True
        if sys.platform == "win32":
            os.startfile(str(path))  # type: ignore[attr-defined]
            return True
    except Exception:  # noqa: BLE001
        return False
    return False


def style_link_spans(
    frags: list[tuple[str, str]],
    plain: str,
    *,
    style: str = "class:transcript-link",
) -> list[tuple[str, str]]:
    """Re-color columns that match path/URL spans with ``style``."""
    spans = iter_link_spans(plain)
    if not spans:
        return frags
    # Expand to per-char then re-merge.
    chars: list[tuple[str, str]] = []
    for frag_style, text in frags:
        for ch in text:
            chars.append((frag_style, ch))
    for start, end, _kind, _target in spans:
        for i in range(start, min(end, len(chars))):
            chars[i] = (style, chars[i][1])
    if not chars:
        return frags
    out: list[tuple[str, str]] = [chars[0]]
    for frag_style, ch in chars[1:]:
        prev_s, prev_t = out[-1]
        if frag_style == prev_s:
            out[-1] = (prev_s, prev_t + ch)
        else:
            out.append((frag_style, ch))
    return out
