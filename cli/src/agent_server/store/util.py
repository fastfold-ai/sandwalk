"""Small stateless helpers shared across the store package."""

from __future__ import annotations

from datetime import UTC, datetime

from agent_server.models import SandboxBackendChoice


def utc_now() -> datetime:
    return datetime.now(UTC)


def parse_sandbox_backend(raw: str | None) -> SandboxBackendChoice | None:
    if raw is None:
        return None
    candidate = str(raw).strip().lower()
    if candidate == "builtin":
        return "builtin"
    if candidate == "modal":
        return "modal"
    return None


def require_sandbox_backend(raw: str | None) -> SandboxBackendChoice:
    parsed = parse_sandbox_backend(raw)
    if parsed is None:
        raise ValueError("sandbox_backend must be 'builtin' or 'modal'")
    return parsed
