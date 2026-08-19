"""Sidebar scope Capy uses when creating chats (All vs a project)."""

from __future__ import annotations

_scope: dict[str, str | None] = {"project_id": None, "session_id": None}


def set_capy_scope(
    *,
    project_id: str | None = None,
    session_id: str | None = None,
) -> dict[str, str | None]:
    _scope["project_id"] = (project_id or "").strip() or None
    _scope["session_id"] = (session_id or "").strip() or None
    return dict(_scope)


def get_capy_scope() -> dict[str, str | None]:
    return dict(_scope)


def format_capy_scope(store) -> str:
    """Text injected into Capy’s prompt so it knows All vs a project."""
    scope = get_capy_scope()
    pid = scope.get("project_id")
    sid = scope.get("session_id")
    if pid:
        project = store.get_project(pid)
        if project is None:
            sidebar = "All chats (no project) — the selected project is gone."
            project_notes = ""
        else:
            sidebar = (
                f"Project “{project.name}” ({project.id}). "
                "New chats you create go in this project unless the user says "
                "All or names another project."
            )
            notes = (project.agent_context or "").strip()
            project_notes = f"\nProject notes:\n{notes}" if notes else ""
    else:
        sidebar = (
            "All chats (no project). New chats you create are unassigned "
            "unless the user names a project."
        )
        project_notes = ""
    chat_line = "No chat selected in the main view."
    if sid:
        session = store.get_session(sid)
        source = str(getattr(session, "source", "") or "") if session else ""
        if session and source not in {"capy", "bench"}:
            chat_line = f"Selected chat: “{session.title}” ({session.id})."
    return f"UI scope:\n- {sidebar}\n- {chat_line}{project_notes}"
