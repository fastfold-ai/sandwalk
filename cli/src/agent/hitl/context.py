"""Per-run HITL context for PTC (programmatic) tool calls.

Default tool mode injects domain tools as Python callables inside
``run_python``, which bypasses LangGraph ``interrupt_on``. Call sites that
need approval read this context at invoke time.
"""

from __future__ import annotations

from contextvars import ContextVar, Token
from dataclasses import dataclass, field
from typing import Any, Callable

ProgressCallback = Callable[..., None] | None


@dataclass(frozen=True)
class HitlRunContext:
    session_id: str | None
    headless: bool
    progress_callback: ProgressCallback
    console: Any = None
    # Mutable set shared by reference for the lifetime of one agent run.
    grants: set[str] = field(default_factory=set)


_CTX: ContextVar[HitlRunContext | None] = ContextVar("hitl_run_context", default=None)


def set_hitl_context(
    *,
    session_id: str | None,
    headless: bool,
    progress_callback: ProgressCallback = None,
    console: Any = None,
) -> Token:
    return _CTX.set(
        HitlRunContext(
            session_id=(session_id or "").strip() or None,
            headless=bool(headless),
            progress_callback=progress_callback,
            console=console,
            grants=set(),
        )
    )


def reset_hitl_context(token: Token) -> None:
    _CTX.reset(token)


def get_hitl_context() -> HitlRunContext | None:
    return _CTX.get()
