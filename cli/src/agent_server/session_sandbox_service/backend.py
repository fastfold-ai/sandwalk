"""Backend selection helpers for per-session sandbox status."""

from __future__ import annotations

from agent.sandbox_backend import sandbox_backend_from_config


def effective_backend(session_backend: str | None, _global_backend: str | None = None) -> str:
    """Resolve the sandbox used for a chat.

    Chats default to Built-in. Modal is used only when the session explicitly
    selects it (composer toggle). Global ``sandbox.backend`` is not inherited.
    """
    if session_backend in {"builtin", "modal"}:
        return session_backend
    return "builtin"


def effective_session_sandbox_backend(
    session_backend: str | None,
    *,
    config: object | None = None,
) -> str:
    from agent.config import Config

    cfg = config or Config.load()
    global_backend = sandbox_backend_from_config(cfg)
    return effective_backend(session_backend, global_backend)
