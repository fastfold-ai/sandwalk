"""Save pasted/dropped images into the session ``uploads/`` tree."""

from __future__ import annotations

import mimetypes
import re
import shutil
from datetime import datetime, timezone
from pathlib import Path

from ui.terminal.clipboard_image import read_clipboard_image

# Image types we attach in v1 (PDF can follow later).
_IMAGE_SUFFIXES = frozenset({
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
    ".heic",
    ".heif",
})

_MIME_TO_EXT = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/gif": ".gif",
    "image/webp": ".webp",
    "image/heic": ".heic",
    "image/heif": ".heif",
}

# Visible chip in the compose buffer; expanded to @uploads/… on submit.
_CHIP_RE = re.compile(r"\[Image\s+(\d+)\]")
_CHIP_LABEL_RE = re.compile(r"\[Image\s+\d+\]")
_UPLOAD_AT_RE = re.compile(
    r"@uploads/[^\s]+?\.(?:png|jpe?g|gif|webp|heic|heif)\b",
    re.IGNORECASE,
)

# Absolute / home / file:// image path at the start of pasted text (optional rest).
_LEADING_PATH_RE = re.compile(
    r"^(?P<path>"
    r"(?:file://[^\s]+)"
    r"|(?:~|/|./|\.\./)[^\n]*?"
    r"\.(?:png|jpe?g|gif|webp|heic|heif)"
    r")(?P<rest>\s+.*)?$",
    re.IGNORECASE | re.DOTALL,
)


def is_image_path(path: Path) -> bool:
    return path.suffix.lower() in _IMAGE_SUFFIXES


def _normalize_path_candidate(raw: str) -> Path | None:
    text = (raw or "").strip().strip("'\"")
    if not text:
        return None
    if text.startswith("file://"):
        from urllib.parse import unquote, urlparse

        parsed = urlparse(text)
        if parsed.scheme != "file":
            return None
        text = unquote(parsed.path)
        if re.match(r"^/[A-Za-z]:/", text):
            text = text[1:]
    path = Path(text).expanduser()
    try:
        path = path.resolve()
    except (OSError, RuntimeError):
        return None
    if not path.is_file() or not is_image_path(path):
        return None
    return path


def parse_pasted_filepath(text: str) -> Path | None:
    """If *text* is a single local image path (or ``file://`` URI), return it."""
    raw = (text or "").strip()
    if not raw or "\n" in raw or "\r" in raw:
        return None
    return _normalize_path_candidate(raw)


def split_pasted_image_path(text: str) -> tuple[Path | None, str]:
    """Split paste into optional leading image path + remaining text.

    Handles Finder/Warp drops that paste ``/path/to.png`` alone or
    ``/path/to.png what's this?``.
    """
    raw = text or ""
    exact = parse_pasted_filepath(raw)
    if exact is not None:
        return exact, ""

    stripped = raw.strip()
    match = _LEADING_PATH_RE.match(stripped)
    if not match:
        return None, raw
    path = _normalize_path_candidate(match.group("path"))
    if path is None:
        return None, raw
    rest = (match.group("rest") or "").lstrip()
    return path, rest


def _safe_stem(name: str) -> str:
    stem = Path(name).stem or "image"
    cleaned = re.sub(r"[^\w.\-]+", "-", stem).strip("-.")
    return (cleaned or "image")[:80]


def _timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")


def save_image_bytes(
    workspace: Path,
    data: bytes,
    *,
    mime: str = "image/png",
    stem: str = "clipboard",
) -> str:
    """Write image bytes under ``uploads/``; return relative token path (no ``@``)."""
    if not data:
        raise ValueError("empty image data")
    uploads = workspace / "uploads"
    uploads.mkdir(parents=True, exist_ok=True)
    ext = _MIME_TO_EXT.get(mime.lower()) or Path(mimetypes.guess_extension(mime) or ".png").suffix
    if ext.lower() not in _IMAGE_SUFFIXES:
        ext = ".png"
    name = f"{_timestamp()}-{_safe_stem(stem)}{ext.lower()}"
    dest = uploads / name
    dest.write_bytes(data)
    return f"uploads/{name}"


def attach_image_file(workspace: Path, source: Path) -> str:
    """Copy an existing image into ``uploads/``; return relative token path."""
    if not source.is_file() or not is_image_path(source):
        raise ValueError(f"not an image file: {source}")
    uploads = workspace / "uploads"
    uploads.mkdir(parents=True, exist_ok=True)
    ext = source.suffix.lower() or ".png"
    name = f"{_timestamp()}-{_safe_stem(source.name)}{ext}"
    dest = uploads / name
    shutil.copy2(source, dest)
    return f"uploads/{name}"


def attach_from_clipboard(workspace: Path) -> str | None:
    """Save clipboard image into uploads; return relative path or None."""
    result = read_clipboard_image()
    if result is None:
        return None
    data, mime = result
    return save_image_bytes(workspace, data, mime=mime, stem="clipboard")


def attach_from_pasted_text(workspace: Path, text: str) -> tuple[str, str] | None:
    """Attach leading image path from paste.

    Returns ``(relative_uploads_path, remaining_text)`` or None.
    """
    path, rest = split_pasted_image_path(text)
    if path is None:
        return None
    return attach_image_file(workspace, path), rest


def chip_label(n: int) -> str:
    return f"[Image {n}]"


def chipify_uploads_for_display(text: str) -> str:
    """Replace ``@uploads/…`` image tokens with ``[Image N]`` for UI display."""
    if not text or not _UPLOAD_AT_RE.search(text):
        return text
    existing = [int(m.group(1)) for m in _CHIP_RE.finditer(text)]
    n = max(existing, default=0)

    def _repl(_match: re.Match[str]) -> str:
        nonlocal n
        n += 1
        return chip_label(n)

    return _UPLOAD_AT_RE.sub(_repl, text)


def style_with_image_chips(
    text: str, base_style: str
) -> list[tuple[str, str]]:
    """Split text into FormattedText fragments, highlighting ``[Image N]`` chips."""
    if not text:
        return [(base_style, "")]
    if not _CHIP_LABEL_RE.search(text):
        return [(base_style, text)]
    out: list[tuple[str, str]] = []
    pos = 0
    for match in _CHIP_LABEL_RE.finditer(text):
        if match.start() > pos:
            out.append((base_style, text[pos : match.start()]))
        out.append(("class:image-chip", match.group(0)))
        pos = match.end()
    if pos < len(text):
        out.append((base_style, text[pos:]))
    return out


def expand_image_chips(text: str, attach_map: dict[int, str]) -> str:
    """Replace ``[Image N]`` chips with ``@uploads/…`` tokens for the agent."""
    if not text or not attach_map:
        return text

    def _repl(match: re.Match[str]) -> str:
        n = int(match.group(1))
        rel = attach_map.get(n)
        if not rel:
            return match.group(0)
        return f"@{rel}"

    return _CHIP_RE.sub(_repl, text)


def rewrite_loose_image_paths(text: str, workspace: Path, attach_map: dict[int, str]) -> tuple[str, dict[int, str]]:
    """On submit: convert leftover absolute image paths into chips/@uploads.

    Safety net when paste attach missed (e.g. non-bracketed paste in Warp).
    """
    if not text:
        return text, attach_map
    out = text
    updated = dict(attach_map)
    # Find absolute/home image paths not already inside @uploads tokens.
    path_re = re.compile(
        r"(?<!@)(?P<path>(?:~|/|./|\.\./)[^\s]*?\.(?:png|jpe?g|gif|webp|heic|heif))",
        re.IGNORECASE,
    )
    next_n = max(updated.keys(), default=0) + 1
    for match in list(path_re.finditer(out)):
        path = _normalize_path_candidate(match.group("path"))
        if path is None:
            continue
        try:
            rel = attach_image_file(workspace, path)
        except (OSError, ValueError):
            continue
        updated[next_n] = rel
        chip = chip_label(next_n)
        out = out[: match.start()] + chip + out[match.end() :]
        next_n += 1
        # Restart scan because offsets shifted
        return rewrite_loose_image_paths(out, workspace, updated)
    return out, updated


def session_workspace_path(terminal) -> Path | None:
    """Resolve the interactive session workspace directory (with fallback)."""
    agent = getattr(terminal, "agent", None)
    if agent is not None:
        ensure = getattr(agent, "ensure_workspace_path", None)
        if ensure is not None:
            try:
                raw = ensure()
            except Exception:
                raw = None
            if raw:
                path = Path(str(raw)).expanduser()
                try:
                    path.mkdir(parents=True, exist_ok=True)
                    return path
                except OSError:
                    pass

    # Fallback so paste attach still works before/without a session workspace.
    try:
        from agent.config import CONFIG_DIR

        fallback = Path(CONFIG_DIR) / "workspaces" / "cli-attach"
        fallback.mkdir(parents=True, exist_ok=True)
        return fallback
    except Exception:
        return None
