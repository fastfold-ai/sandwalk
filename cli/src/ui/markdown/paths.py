"""Prefer full local paths in markdown so terminals can open them.

Rich does not turn ``file://`` markdown links into OSC-8 hyperlinks (https only).
Warp and similar hosts often auto-link bare absolute paths — so we unwrap
backtick-wrapped path-like spans to absolute plain text, and never invent
ellipsis truncations here (the model must emit full paths).
"""

from __future__ import annotations

import os
import re
from pathlib import Path

# `artifacts/foo/bar.cif` or `/Users/.../file` or ~/Projects/...
_CODE_SPAN = re.compile(r"`([^`\n]+)`")
_PATHISH = re.compile(
    r"^(?:~|/|\./|\.\./|[A-Za-z]:\\)"
    r"|^(?:artifacts|outputs|uploads|plans|skills)/"
    r"|[/\\][^`\n]*\.[A-Za-z0-9]{1,12}$"
)


def looks_like_local_path(value: str) -> bool:
    text = str(value or "").strip()
    if not text or "://" in text and not text.startswith("file:"):
        return False
    if text.startswith(("http://", "https://", "mailto:")):
        return False
    # Truncated model output — leave as-is (cannot expand).
    if "..." in text or "…" in text:
        return False
    if " " in text and not text.startswith(("/", "~", ".")):
        return False
    # Slash-commands (`/help`, `/models`) are not filesystem paths.
    if re.fullmatch(r"/[A-Za-z][\w.-]*", text):
        return False
    return bool(_PATHISH.search(text)) or ("/" in text and "." in Path(text).name)


def resolve_local_path(value: str, *, workspace: str | None = None) -> str:
    text = str(value or "").strip()
    if text.startswith("file://"):
        text = text[7:]
    expanded = os.path.expanduser(text)
    path = Path(expanded)
    if path.is_absolute():
        return str(path)
    root = str(workspace or "").strip()
    if root:
        return str((Path(root) / expanded).resolve())
    try:
        return str(path.resolve())
    except Exception:  # noqa: BLE001
        return expanded


def unwrap_path_code_spans(text: str, *, workspace: str | None = None) -> str:
    """Turn `` `rel/or/abs/path` `` into a bare absolute path for click-to-open."""

    def repl(match: re.Match[str]) -> str:
        inner = match.group(1).strip()
        if not looks_like_local_path(inner):
            return match.group(0)
        return resolve_local_path(inner, workspace=workspace)

    return _CODE_SPAN.sub(repl, str(text or ""))
