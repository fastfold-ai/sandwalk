"""Formatting helpers shared by sandbox control tool coroutines."""

from __future__ import annotations

import json
from typing import Any

SANDBOX_CONTROL_TOOL_NAMES = (
    "sandbox_status",
    "sandbox_start",
    "sandbox_stop",
)


def status_payload(status: Any) -> dict[str, Any]:
    if hasattr(status, "model_dump"):
        data = status.model_dump()
    elif isinstance(status, dict):
        data = dict(status)
    else:
        data = {
            "session_id": getattr(status, "session_id", None),
            "backend": getattr(status, "backend", None),
            "status": getattr(status, "status", None),
            "detail": getattr(status, "detail", None),
        }
    return data


def format_status(status: Any, *, summary: str) -> str:
    payload = status_payload(status)
    return f"{summary}\nDetails: {json.dumps(payload, ensure_ascii=True)}"
