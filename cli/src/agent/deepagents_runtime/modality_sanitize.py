"""Strip unsupported multimodal content blocks before provider calls.

Text-only APIs (DeepSeek, many local LLMs) reject OpenAI-style ``image_url``
blocks that MCP tools (e.g. viewport captures) inject into ToolMessages.
This middleware runs on every model request and replaces unsupported media
with a short text stub so the turn continues.
"""

from __future__ import annotations

import base64
import hashlib
import logging
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

from langchain.agents.middleware.types import AgentMiddleware

from agent.model_catalog.modality_support import (
    ModalityKind,
    model_supports_modality,
)

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from langchain.agents.middleware.types import (
        ExtendedModelResponse,
        ModelRequest,
        ModelResponse,
        ResponseT,
    )
    from langchain_core.messages import AIMessage

logger = logging.getLogger("deepagents_runtime.modality")

_ALL_KINDS: tuple[ModalityKind, ...] = ("image", "file", "audio", "video")
_DATA_URL_RE = re.compile(
    r"^data:([^;]+);base64,(.+)$",
    re.IGNORECASE | re.DOTALL,
)
_MIME_EXT = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/jpg": ".jpg",
    "image/gif": ".gif",
    "image/webp": ".webp",
    "application/pdf": ".pdf",
    "audio/wav": ".wav",
    "audio/mpeg": ".mp3",
    "video/mp4": ".mp4",
}


def _block_dict(block: Any) -> dict[str, Any] | None:
    if isinstance(block, dict):
        return block
    # Rare: pydantic content models with model_dump.
    dump = getattr(block, "model_dump", None)
    if callable(dump):
        try:
            data = dump()
        except Exception:  # noqa: BLE001
            return None
        return data if isinstance(data, dict) else None
    return None


def detect_block_modality(block: Any) -> ModalityKind | None:
    """Return modality kind for a LangChain/OpenAI content block, if any."""
    data = _block_dict(block)
    if data is None:
        return None
    kind = str(data.get("type") or "").strip().lower()
    if kind in {"image", "image_url"}:
        return "image"
    if kind in {"file", "document"}:
        return "file"
    if kind == "audio":
        return "audio"
    if kind == "video":
        return "video"
    if "image_url" in data:
        return "image"
    mime = str(
        data.get("mime_type") or data.get("mimeType") or data.get("media_type") or ""
    ).strip().lower()
    if mime.startswith("image/"):
        return "image"
    if mime.startswith("audio/"):
        return "audio"
    if mime.startswith("video/"):
        return "video"
    if mime in {"application/pdf", "application/x-pdf"}:
        return "file"
    return None


def _extract_bytes_and_mime(data: dict[str, Any]) -> tuple[bytes | None, str]:
    mime = str(
        data.get("mime_type") or data.get("mimeType") or data.get("media_type") or ""
    ).strip().lower()
    raw_b64 = data.get("base64") or data.get("data")
    if isinstance(raw_b64, str) and raw_b64.strip():
        try:
            return base64.b64decode(raw_b64, validate=False), mime or "application/octet-stream"
        except Exception:  # noqa: BLE001
            return None, mime

    image_url = data.get("image_url")
    url = ""
    if isinstance(image_url, dict):
        url = str(image_url.get("url") or "")
    elif isinstance(image_url, str):
        url = image_url
    if not url:
        url = str(data.get("url") or "")
    match = _DATA_URL_RE.match(url.strip())
    if match:
        mime = mime or match.group(1).strip().lower()
        try:
            return base64.b64decode(match.group(2), validate=False), mime
        except Exception:  # noqa: BLE001
            return None, mime
    return None, mime


def _save_media(
    data: dict[str, Any],
    *,
    kind: ModalityKind,
    save_dir: Path | None,
) -> str | None:
    if save_dir is None:
        return None
    payload, mime = _extract_bytes_and_mime(data)
    if not payload:
        return None
    try:
        save_dir.mkdir(parents=True, exist_ok=True)
    except OSError:
        return None
    ext = _MIME_EXT.get(mime) or {
        "image": ".png",
        "file": ".bin",
        "audio": ".bin",
        "video": ".bin",
    }.get(kind, ".bin")
    digest = hashlib.sha256(payload).hexdigest()[:16]
    path = save_dir / f"{kind}-{digest}{ext}"
    try:
        if not path.exists():
            path.write_bytes(payload)
    except OSError:
        return None
    return str(path)


def _stub_text(kind: ModalityKind, saved_path: str | None) -> str:
    where = f" Saved to `{saved_path}`." if saved_path else ""
    return (
        f"[{kind.capitalize()} omitted: this model cannot accept {kind} input "
        f"in the chat request.{where} Infer from tool text / session state, "
        f"or switch to a vision-capable model to inspect the media.]"
    )


def sanitize_content_blocks(
    content: Any,
    *,
    unsupported: frozenset[ModalityKind],
    save_dir: Path | None = None,
) -> tuple[Any, bool]:
    """Replace unsupported media blocks with text stubs.

    Returns ``(new_content, changed)``.
    """
    if not unsupported or not isinstance(content, list):
        return content, False

    kept: list[Any] = []
    changed = False
    for block in content:
        data = _block_dict(block)
        kind = detect_block_modality(block) if data is not None else None
        if kind is None or kind not in unsupported:
            kept.append(block)
            continue
        changed = True
        saved = _save_media(data or {}, kind=kind, save_dir=save_dir)
        kept.append({"type": "text", "text": _stub_text(kind, saved)})

    if not changed:
        return content, False
    # Providers reject empty content; keep a single stub if everything was media.
    if not kept:
        kept.append(
            {
                "type": "text",
                "text": "[Media omitted: model does not support multimodal input.]",
            }
        )
    return kept, True


def sanitize_messages(
    messages: list[Any],
    *,
    unsupported: frozenset[ModalityKind],
    save_dir: Path | None = None,
) -> tuple[list[Any], bool]:
    """Return messages with unsupported media stripped from list content."""
    if not unsupported or not messages:
        return messages, False

    out: list[Any] = []
    changed = False
    for message in messages:
        content = getattr(message, "content", None)
        new_content, msg_changed = sanitize_content_blocks(
            content, unsupported=unsupported, save_dir=save_dir
        )
        if not msg_changed:
            out.append(message)
            continue
        changed = True
        copy = getattr(message, "model_copy", None)
        if callable(copy):
            out.append(copy(update={"content": new_content}))
        else:
            try:
                message.content = new_content
            except Exception:  # noqa: BLE001
                out.append(message)
                continue
            out.append(message)
    return out, changed


def unsupported_modalities(
    provider: str | None,
    model_id: str | None,
    *,
    profile: Any = None,
) -> frozenset[ModalityKind]:
    """Modalities the provider/model must not receive as native content blocks."""
    return frozenset(
        kind
        for kind in _ALL_KINDS
        if not model_supports_modality(provider, model_id, kind, profile=profile)
    )


class UnsupportedModalityMiddleware(AgentMiddleware[Any, Any, Any]):
    """Drop unsupported image/file/audio/video blocks before the provider call."""

    def __init__(
        self,
        *,
        provider: str | None,
        model_id: str | None,
        workspace_path: str | None = None,
        profile: Any = None,
    ) -> None:
        self._unsupported = unsupported_modalities(
            provider, model_id, profile=profile
        )
        root = str(workspace_path or "").strip()
        self._save_dir = (
            Path(root).expanduser().resolve() / "artifacts" / "tool-images"
            if root
            else None
        )
        self._provider = str(provider or "")
        self._model_id = str(model_id or "")

    def _filter_request(self, request: "ModelRequest[Any]") -> "ModelRequest[Any]":
        if not self._unsupported:
            return request
        messages, changed = sanitize_messages(
            list(request.messages or []),
            unsupported=self._unsupported,
            save_dir=self._save_dir,
        )
        if not changed:
            return request
        logger.info(
            "Stripped unsupported multimodal blocks for %s/%s (kinds=%s)",
            self._provider or "?",
            self._model_id or "?",
            ",".join(sorted(self._unsupported)),
        )
        return request.override(messages=messages)

    def wrap_model_call(
        self,
        request: "ModelRequest[Any]",
        handler: "Callable[[ModelRequest[Any]], ModelResponse[Any]]",
    ) -> "ModelResponse[Any]":
        return handler(self._filter_request(request))

    async def awrap_model_call(
        self,
        request: "ModelRequest[Any]",
        handler: "Callable[[ModelRequest[Any]], Awaitable[ModelResponse[ResponseT]]]",
    ) -> "ModelResponse[ResponseT] | AIMessage | ExtendedModelResponse[ResponseT]":
        return await handler(self._filter_request(request))
