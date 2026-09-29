"""FAS-107 — workspace_items index + terminal_sessions CRUD.

Covers the fan-out contract: every chat / terminal mutation keeps the
denormalized ``workspace_items`` mirror row in sync so the tab strip and
sidebar can query one indexed table instead of UNIONing per kind.
"""

from __future__ import annotations

from pathlib import Path

from agent_server.store import AgentStore


def test_chat_create_mirrors_into_workspace_items(tmp_path: Path):
    store = AgentStore(tmp_path / "agent.db")
    try:
        project = store.create_project(name="Sandwalk", folder_path=None)
        chat = store.create_session(
            title="Refactor auth",
            workspace_path=None,
            project_id=project.id,
        )
        mirror = store.get_workspace_item(chat.id)
        assert mirror is not None
        assert mirror.kind == "chat"
        assert mirror.title == "Refactor auth"
        assert mirror.project_id == project.id
    finally:
        store.close()


def test_chat_update_bumps_workspace_items(tmp_path: Path):
    store = AgentStore(tmp_path / "agent.db")
    try:
        project = store.create_project(name="Sandwalk", folder_path=None)
        chat = store.create_session(
            title="Refactor auth", workspace_path=None, project_id=project.id
        )
        store.update_session(chat.id, title="New name")
        mirror = store.get_workspace_item(chat.id)
        assert mirror is not None
        assert mirror.title == "New name"
    finally:
        store.close()


def test_chat_delete_removes_workspace_item(tmp_path: Path):
    store = AgentStore(tmp_path / "agent.db")
    try:
        chat = store.create_session(title="Chat", workspace_path=None)
        assert store.get_workspace_item(chat.id) is not None
        store.delete_session(chat.id)
        assert store.get_workspace_item(chat.id) is None
    finally:
        store.close()


def test_terminal_create_uses_default_title_and_mirrors(tmp_path: Path):
    store = AgentStore(tmp_path / "agent.db")
    try:
        project = store.create_project(name="Sandwalk", folder_path=None)
        term = store.create_terminal(project_id=project.id, workspace_path="/tmp")
        assert term.title == "Terminal 1"
        assert term.title_source == "pending"
        assert term.status == "idle"
        mirror = store.get_workspace_item(term.id)
        assert mirror is not None
        assert mirror.kind == "terminal"
        assert mirror.title == "Terminal 1"
        assert mirror.project_id == project.id

        term2 = store.create_terminal(project_id=project.id, workspace_path="/tmp")
        assert term2.title == "Terminal 2"
    finally:
        store.close()


def test_terminal_explicit_title_marks_user_source(tmp_path: Path):
    store = AgentStore(tmp_path / "agent.db")
    try:
        term = store.create_terminal(title="Deploy shell", workspace_path="/tmp")
        assert term.title == "Deploy shell"
        assert term.title_source == "user"
    finally:
        store.close()


def test_terminal_update_syncs_index_title(tmp_path: Path):
    store = AgentStore(tmp_path / "agent.db")
    try:
        term = store.create_terminal(workspace_path="/tmp")
        updated = store.update_terminal(term.id, title="Renamed")
        assert updated is not None
        assert updated.title == "Renamed"
        assert updated.title_source == "user"
        mirror = store.get_workspace_item(term.id)
        assert mirror is not None
        assert mirror.title == "Renamed"
    finally:
        store.close()


def test_terminal_delete_removes_workspace_item(tmp_path: Path):
    store = AgentStore(tmp_path / "agent.db")
    try:
        term = store.create_terminal(workspace_path="/tmp")
        assert store.get_workspace_item(term.id) is not None
        assert store.delete_terminal(term.id) is True
        assert store.get_workspace_item(term.id) is None
        assert store.delete_terminal(term.id) is False
    finally:
        store.close()


def test_list_workspace_items_returns_mixed_kinds_by_project(tmp_path: Path):
    store = AgentStore(tmp_path / "agent.db")
    try:
        project = store.create_project(name="Sandwalk", folder_path=None)
        chat = store.create_session(
            title="Chat A", workspace_path=None, project_id=project.id
        )
        term = store.create_terminal(project_id=project.id, workspace_path="/tmp")
        items = store.list_workspace_items(project_id=project.id)
        kinds_by_id = {item.id: item.kind for item in items}
        assert kinds_by_id.get(chat.id) == "chat"
        assert kinds_by_id.get(term.id) == "terminal"
    finally:
        store.close()


def test_list_workspace_items_filters_by_kind(tmp_path: Path):
    store = AgentStore(tmp_path / "agent.db")
    try:
        project = store.create_project(name="Sandwalk", folder_path=None)
        chat = store.create_session(
            title="Chat A", workspace_path=None, project_id=project.id
        )
        term = store.create_terminal(project_id=project.id, workspace_path="/tmp")
        only_terms = store.list_workspace_items(
            project_id=project.id, kinds=["terminal"]
        )
        assert [item.id for item in only_terms] == [term.id]
        only_chats = store.list_workspace_items(
            project_id=project.id, kinds=["chat"]
        )
        assert [item.id for item in only_chats] == [chat.id]
    finally:
        store.close()


def test_workspace_items_backfill_covers_pre_existing_chats(tmp_path: Path):
    """Chats created before FAS-107 must appear in the index after a
    subsequent open — the migration backfills them."""
    db = tmp_path / "agent.db"
    store = AgentStore(db)
    try:
        # Simulate a chat that predates FAS-107 by writing straight to the
        # sessions table and skipping the write-through.
        with store._write_lock, store._connect() as connection:
            connection.execute(
                """
                INSERT INTO sessions(
                    id, title, title_source, status, organize_label, project_id,
                    specialist_id, sandbox_backend, provider, model,
                    openai_profile_id, workspace_path, source, source_label,
                    client_surface, last_message_at, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "legacy_chat_1",
                    "Legacy chat",
                    "user",
                    "idle",
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    None,
                    "unknown",
                    None,
                    "2026-08-01T00:00:00+00:00",
                    "2026-08-01T00:00:00+00:00",
                ),
            )
            connection.execute(
                "DELETE FROM workspace_items WHERE id = 'legacy_chat_1'"
            )
    finally:
        store.close()

    reopened = AgentStore(db)
    try:
        mirror = reopened.get_workspace_item("legacy_chat_1")
        assert mirror is not None
        assert mirror.kind == "chat"
        assert mirror.title == "Legacy chat"
    finally:
        reopened.close()
