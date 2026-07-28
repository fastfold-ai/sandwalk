"""Project folder validation, appearance defaults, and workspace mounts."""

from __future__ import annotations

from pathlib import Path

import pytest

from agent_server.project_folder import (
    sync_project_folder_link,
    validate_project_folder_path,
)
from agent_server.service import AgentService
from agent_server.store import AgentStore


def test_path_under_workspace_or_project_allows_mount(tmp_path: Path):
    import os

    from agent_server.project_folder import (
        path_under_workspace_or_project,
        workspace_rel_via_project_mount,
    )

    workspace = tmp_path / "ws"
    workspace.mkdir()
    linked = tmp_path / "linked"
    linked.mkdir()
    (linked / "backlog.md").write_text("x\n", encoding="utf-8")
    os.symlink(linked, workspace / "project", target_is_directory=True)

    via_mount = path_under_workspace_or_project(
        workspace / "project" / "backlog.md", workspace
    )
    assert via_mount == (linked / "backlog.md").resolve()
    assert (
        workspace_rel_via_project_mount(via_mount, workspace) == "project/backlog.md"
    )
    # Direct absolute path into the linked folder is rejected.
    assert path_under_workspace_or_project(linked / "backlog.md", workspace) is None


def test_path_under_workspace_or_project_var_private_alias(tmp_path: Path):
    """Lexical checks must tolerate macOS /var vs /private/var."""
    import os

    from agent_server.project_folder import path_under_workspace_or_project

    workspace = tmp_path / "ws"
    workspace.mkdir()
    linked = tmp_path / "linked"
    linked.mkdir()
    (linked / "backlog.md").write_text("x\n", encoding="utf-8")
    os.symlink(linked, workspace / "project", target_is_directory=True)

    resolved_ws = workspace.resolve()
    # Build a /var/... form when resolve() produced /private/var/...
    text = str(resolved_ws / "project" / "backlog.md")
    if text.startswith("/private/var/"):
        aliased = Path(text[len("/private") :])
        assert path_under_workspace_or_project(aliased, workspace) is not None
    else:
        # Non-macOS / non-/var temp dirs: still accept the normal path.
        assert (
            path_under_workspace_or_project(
                workspace / "project" / "backlog.md", workspace
            )
            is not None
        )


def test_validate_project_folder_path_requires_existing_directory(tmp_path: Path):
    folder = tmp_path / "data"
    folder.mkdir()
    assert validate_project_folder_path(str(folder)) == str(folder.resolve())
    assert validate_project_folder_path("  ") is None
    assert validate_project_folder_path(None) is None

    missing = tmp_path / "missing"
    with pytest.raises(ValueError, match="does not exist"):
        validate_project_folder_path(str(missing))

    file_path = tmp_path / "notes.txt"
    file_path.write_text("x", encoding="utf-8")
    with pytest.raises(ValueError, match="must be a directory"):
        validate_project_folder_path(str(file_path))


def test_sync_project_folder_link_create_retarget_clear(tmp_path: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    first = tmp_path / "first"
    second = tmp_path / "second"
    first.mkdir()
    second.mkdir()

    sync_project_folder_link(workspace, str(first))
    link = workspace / "project"
    assert link.is_symlink()
    assert link.resolve() == first.resolve()

    sync_project_folder_link(workspace, str(second))
    assert link.is_symlink()
    assert link.resolve() == second.resolve()

    sync_project_folder_link(workspace, None)
    assert not link.exists()


def test_sync_project_folder_link_does_not_clobber_real_directory(tmp_path: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    real = workspace / "project"
    real.mkdir()
    (real / "keep.txt").write_text("keep", encoding="utf-8")
    target = tmp_path / "linked"
    target.mkdir()

    sync_project_folder_link(workspace, str(target))
    assert real.is_dir() and not real.is_symlink()
    assert (real / "keep.txt").read_text(encoding="utf-8") == "keep"


def test_project_folder_crud_and_icon_persistence(tmp_path: Path):
    store = AgentStore(tmp_path / "agent.db")
    folder = tmp_path / "campaign"
    folder.mkdir()

    created = store.create_project(
        name="Campaign",
        folder_path=str(folder),
        icon="flask",
        color="blue",
    )
    assert created.folder_path == str(folder.resolve())
    assert created.icon == "flask"
    assert created.color == "blue"

    fetched = store.get_project(created.id)
    assert fetched is not None
    assert fetched.icon == "flask"
    assert fetched.color == "blue"
    assert fetched.folder_path == str(folder.resolve())

    updated = store.update_project(
        created.id,
        icon="brain",
        color="purple",
        folder_path=None,
        update_folder_path=True,
    )
    assert updated is not None
    assert updated.icon == "brain"
    assert updated.color == "purple"
    assert updated.folder_path is None


def test_ensure_workspace_mounts_project_folder(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("agent_server.service.CONFIG_DIR", tmp_path / "cfg")
    store = AgentStore(tmp_path / "agent.db")
    folder = tmp_path / "shared"
    folder.mkdir()
    (folder / "readme.md").write_text("hello", encoding="utf-8")

    project = store.create_project(name="Shared", folder_path=str(folder))
    store.ensure_session("sess-mount", title="Mount", project_id=project.id)

    service = AgentService(store)
    session = service.ensure_workspace("sess-mount")
    link = Path(session.workspace_path) / "project"
    assert link.is_symlink()
    assert link.resolve() == folder.resolve()
    assert (link / "readme.md").read_text(encoding="utf-8") == "hello"

    store.update_project(
        project.id,
        folder_path=None,
        update_folder_path=True,
    )
    service.ensure_workspace("sess-mount")
    assert not link.exists()
