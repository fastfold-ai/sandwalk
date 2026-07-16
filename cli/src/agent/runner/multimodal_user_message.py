"""Build LangChain/Deep Agents multimodal user ``content`` from workspace @paths.

Stored chat remains a plain string with ``@path`` references. At invoke time we
expand supported multimodal files into standard content blocks when the model
accepts that modality.
"""

from __future__ import annotations

import base64
import logging
import mimetypes
import re
from pathlib import Path
from typing import Any

from agent.model_catalog.modality_support import (
    ModalityKind,
    modality_for_extension,
    model_supports_modality,
)

logger = logging.getLogger("runner.multimodal")

# Match @path tokens including spaces in filenames (macOS screenshots, etc.).
# Path segments may contain spaces; stop at common trailing punctuation.
_AT_PATH_RE = re.compile(
    r"(?<![\w./])@("
    r"(?:[^@\n]+?/)*"
    r"[^@\n/]+?\.(?:"
    r"png|jpe?g|gif|webp|heic|heif|"
    r"pdf|pptx?|"
    r"wav|mp3|aiff|aac|ogg|flac|"
    r"mp4|mpeg|mov|avi|flv|mpg|webm|wmv|3gpp"
    r")"
    r")(?=[\s?!,;:\"')\]]|$)",
    re.IGNORECASE,
)

_DEFAULT_MIME: dict[str, str] = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".heic": "image/heic",
    ".heif": "image/heif",
    ".pdf": "application/pdf",
    ".ppt": "application/vnd.ms-powerpoint",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".wav": "audio/wav",
    ".mp3": "audio/mpeg",
    ".aiff": "audio/aiff",
    ".aac": "audio/aac",
    ".ogg": "audio/ogg",
    ".flac": "audio/flac",
    ".mp4": "video/mp4",
    ".mpeg": "video/mpeg",
    ".mpg": "video/mpeg",
    ".mov": "video/quicktime",
    ".avi": "video/x-msvideo",
    ".flv": "video/x-flv",
    ".webm": "video/webm",
    ".wmv": "video/x-ms-wmv",
    ".3gpp": "video/3gpp",
}

_MAX_BYTES: dict[ModalityKind, int] = {
    "image": 20 * 1024 * 1024,
    "file": 20 * 1024 * 1024,
    "audio": 20 * 1024 * 1024,
    "video": 40 * 1024 * 1024,
}


def extract_multimodal_paths(user_prompt: str) -> list[str]:
    """Return unique relative paths referenced via ``@path`` in the prompt."""
    found: list[str] = []
    seen: set[str] = set()
    for match in _AT_PATH_RE.finditer(str(user_prompt or "")):
        rel = match.group(1).replace("\\", "/").lstrip("/")
        if not rel or rel in seen:
            continue
        seen.add(rel)
        found.append(rel)
    return found


def _resolve_under_workspace(workspace_root: Path, relative: str) -> Path | None:
    try:
        root = workspace_root.resolve()
        candidate = (root / relative).resolve()
    except (OSError, RuntimeError):
        return None
    try:
        candidate.relative_to(root)
    except ValueError:
        return None
    if not candidate.is_file():
        return None
    return candidate


def _mime_for(path: Path) -> str:
    ext = path.suffix.lower()
    guessed, _ = mimetypes.guess_type(path.name)
    return guessed or _DEFAULT_MIME.get(ext) or "application/octet-stream"


def _build_block(kind: ModalityKind, path: Path, data: bytes) -> dict[str, Any]:
    mime = _mime_for(path)
    b64 = base64.b64encode(data).decode("ascii")
    block: dict[str, Any] = {
        "type": kind,
        "base64": b64,
        "mime_type": mime,
    }
    if kind == "file":
        # OpenAI requires a filename for PDF/document inputs.
        block["filename"] = path.name
    return block


def build_multimodal_user_content(
    user_prompt: str,
    *,
    workspace_root: str | Path | None,
    provider: str | None,
    model_id: str | None,
    profile: Any = None,
) -> str | list[dict[str, Any]]:
    """Return multimodal content list or the original string when nothing injects."""
    text = str(user_prompt or "")
    if not text.strip() or not workspace_root:
        return text

    root = Path(str(workspace_root)).expanduser()
    if not root.is_dir():
        return text

    paths = extract_multimodal_paths(text)
    if not paths:
        return text

    blocks: list[dict[str, Any]] = []
    notes: list[str] = []

    for rel in paths:
        kind = modality_for_extension(Path(rel).suffix)
        if kind is None:
            continue
        if not model_supports_modality(provider, model_id, kind, profile=profile):
            continue
        resolved = _resolve_under_workspace(root, rel)
        if resolved is None:
            notes.append(f"(Could not read attached file `{rel}` for multimodal input.)")
            continue
        max_bytes = _MAX_BYTES[kind]
        try:
            size = resolved.stat().st_size
        except OSError:
            notes.append(f"(Could not stat attached file `{rel}`.)")
            continue
        if size > max_bytes:
            notes.append(
                f"(Skipped `{rel}`: exceeds {max_bytes // (1024 * 1024)}MB multimodal limit.)"
            )
            continue
        try:
            data = resolved.read_bytes()
        except OSError as exc:
            logger.warning("Failed reading multimodal attachment %s: %s", rel, exc)
            notes.append(f"(Could not read attached file `{rel}`.)")
            continue
        blocks.append(_build_block(kind, resolved, data))

    if not blocks:
        return text

    prompt_text = text
    if notes:
        prompt_text = text + "\n\n" + "\n".join(notes)

    # Steer the agentic loop away from tool-based decode when bytes are already
    # in the user message (common failure mode: model calls whisper/ffmpeg).
    kinds_present = {str(b.get("type") or "") for b in blocks}
    if kinds_present & {"audio", "video", "image", "file"}:
        hint_bits: list[str] = []
        if "audio" in kinds_present:
            hint_bits.append(
                "Audio is attached as native multimodal input — listen/"
                "transcribe it directly. Do not require whisper, pydub, "
                "librosa, or local audio packages."
            )
        if "video" in kinds_present:
            hint_bits.append(
                "Video is attached as native multimodal input — watch/"
                "describe it directly without local media tooling."
            )
        if "image" in kinds_present:
            hint_bits.append(
                "Image(s) are attached as native multimodal input — describe "
                "them directly."
            )
        if "file" in kinds_present:
            hint_bits.append(
                "Document file(s) are attached as native multimodal input — "
                "read them directly."
            )
        if hint_bits:
            prompt_text = prompt_text + "\n\n" + "\n".join(hint_bits)

    return [{"type": "text", "text": prompt_text}, *blocks]
