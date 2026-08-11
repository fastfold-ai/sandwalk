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


class MultimodalInjectionError(RuntimeError):
    """Raised when the user attached media that must be injected but was not."""


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
    require_injection: bool = True,
) -> str | list[dict[str, Any]]:
    """Return multimodal content list or the original string when nothing injects.

    When ``require_injection`` is True (default) and the prompt references image
    attachments that the model is marked as able to view, but no image bytes
    are injected, raises ``MultimodalInjectionError`` instead of silently
    sending text-only (which causes domain hallucinations).
    """
    text = str(user_prompt or "")
    if not text.strip():
        return text

    paths = extract_multimodal_paths(text)
    if not paths:
        return text

    image_paths = [
        rel
        for rel in paths
        if modality_for_extension(Path(rel).suffix) == "image"
    ]
    vision_model = bool(
        image_paths
        and model_supports_modality(
            provider, model_id, "image", profile=profile
        )
    )

    if not workspace_root:
        if require_injection and vision_model:
            raise MultimodalInjectionError(
                "Image attachment(s) were not sent to the model: session "
                "workspace path is missing, so pixels could not be loaded. "
                f"Referenced: {', '.join(image_paths)}"
            )
        return text

    root = Path(str(workspace_root)).expanduser()
    if not root.is_dir():
        if require_injection and vision_model:
            raise MultimodalInjectionError(
                "Image attachment(s) were not sent to the model: workspace "
                f"directory does not exist ({root}). "
                f"Referenced: {', '.join(image_paths)}"
            )
        return text

    blocks: list[dict[str, Any]] = []
    notes: list[str] = []
    skipped_unsupported: list[str] = []
    failed_image_reasons: list[str] = []

    for rel in paths:
        kind = modality_for_extension(Path(rel).suffix)
        if kind is None:
            continue
        if not model_supports_modality(provider, model_id, kind, profile=profile):
            skipped_unsupported.append(rel)
            continue
        resolved = _resolve_under_workspace(root, rel)
        if resolved is None:
            msg = f"Could not read attached file `{rel}` for multimodal input."
            notes.append(f"({msg})")
            if kind == "image":
                failed_image_reasons.append(msg)
            continue
        max_bytes = _MAX_BYTES[kind]
        try:
            size = resolved.stat().st_size
        except OSError:
            msg = f"Could not stat attached file `{rel}`."
            notes.append(f"({msg})")
            if kind == "image":
                failed_image_reasons.append(msg)
            continue
        if size > max_bytes:
            msg = (
                f"Skipped `{rel}`: exceeds "
                f"{max_bytes // (1024 * 1024)}MB multimodal limit."
            )
            notes.append(f"({msg})")
            if kind == "image":
                failed_image_reasons.append(msg)
            continue
        try:
            data = resolved.read_bytes()
        except OSError as exc:
            logger.warning("Failed reading multimodal attachment %s: %s", rel, exc)
            msg = f"Could not read attached file `{rel}`."
            notes.append(f"({msg})")
            if kind == "image":
                failed_image_reasons.append(msg)
            continue
        blocks.append(_build_block(kind, resolved, data))

    injected_images = sum(1 for b in blocks if b.get("type") == "image")
    if require_injection and vision_model and injected_images == 0:
        detail = "; ".join(failed_image_reasons) or "unknown reason"
        raise MultimodalInjectionError(
            "Image attachment(s) were not sent to the model as native "
            "multimodal input, so the model cannot see the pixels. "
            f"Provider={provider!r} model={model_id!r}. {detail}"
        )

    if skipped_unsupported:
        notes.append(
            "(These attachments were NOT sent as multimodal input because "
            f"the active model is not marked as supporting them: "
            f"{', '.join(skipped_unsupported)}. Switch to a vision model or "
            "use tools to inspect the files.)"
        )

    if not blocks:
        if notes:
            return text + "\n\n" + "\n".join(notes)
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
                "the actual visible content first. Do not invent scientific "
                "plots, assays, chemical structures, or dose–response "
                "interpretations that are not in the image."
            )
        if "file" in kinds_present:
            hint_bits.append(
                "Document file(s) are attached as native multimodal input — "
                "read them directly."
            )
        if hint_bits:
            prompt_text = prompt_text + "\n\n" + "\n".join(hint_bits)

    total_bytes = sum(len(base64.b64decode(b["base64"])) for b in blocks if "base64" in b)
    logger.info(
        "Injected multimodal content: provider=%s model=%s blocks=%s "
        "images=%s bytes=%s",
        provider,
        model_id,
        len(blocks),
        injected_images,
        total_bytes,
    )

    return [{"type": "text", "text": prompt_text}, *blocks]
