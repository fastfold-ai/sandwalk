"""Secret/path redaction helpers shared by diagnostics collectors."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

_SECRET_KEY_RE = re.compile(
    r"(key|token|secret|password|passwd|authorization|api[_-]?key|oidc)",
    re.IGNORECASE,
)
_SECRET_VALUE_RE = re.compile(
    r"(?i)\b(sk-[A-Za-z0-9_\-]{8,}|sk_ant-[A-Za-z0-9_\-]{8,}|"
    r"sk_bc_[A-Za-z0-9_\-]{8,}|sk-fdg[A-Za-z0-9_\-]{8,}|"
    r"eyJ[A-Za-z0-9_\-]{20,}\.[A-Za-z0-9_\-]{10,})"
)
_HOME = str(Path.home())


def _redact_text(text: str) -> str:
    # Resolved lazily via the package attribute so tests can monkeypatch
    # `agent.diagnostics._HOME`.
    from agent import diagnostics as _pkg

    value = text.replace(_pkg._HOME, "~")
    value = _SECRET_VALUE_RE.sub("<redacted-secret>", value)
    # Common absolute project paths → keep basename-ish but hide username home.
    value = re.sub(r"/Users/[^/\s]+", "~", value)
    value = re.sub(r"/home/[^/\s]+", "~", value)
    return value


def _redact_obj(value: Any, *, key: str = "") -> Any:
    if isinstance(value, dict):
        return {k: _redact_obj(v, key=str(k)) for k, v in value.items()}
    if isinstance(value, list):
        return [_redact_obj(item, key=key) for item in value]
    if isinstance(value, str):
        if _SECRET_KEY_RE.search(key) and value.strip():
            return "<redacted>"
        return _redact_text(value)
    return value
