"""Get-or-create the singleton Capy chat (source=capy)."""

from __future__ import annotations

from agent_server.capy import CAPY_SOURCE, CAPY_TITLE, is_capy_session
from agent_server.models import AgentSession


def get_or_create_capy_session(store, service) -> AgentSession:
    existing = store.get_session_by_source(CAPY_SOURCE)
    if existing is not None and is_capy_session(existing):
        return existing
    return service.create_session(
        title=CAPY_TITLE,
        workspace_path=None,
        source=CAPY_SOURCE,
        source_label="Capy",
        sandbox_backend="builtin",
        client_surface="ui",
    )


def reset_capy_session(store, service) -> AgentSession:
    session = get_or_create_capy_session(store, service)
    try:
        service.interrupt(session.id)
    except Exception:  # noqa: BLE001
        pass
    store.clear_messages(session.id)
    store.clear_events(session.id)
    store.set_session_status(session.id, "idle")
    return store.get_session(session.id) or session
