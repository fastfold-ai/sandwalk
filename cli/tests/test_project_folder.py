"""Project folder validation, appearance defaults, and workspace mounts."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from agent_server.app import create_app
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


def test_list_and_read_project_folder_files(tmp_path: Path):
    from agent_server.project_folder_listing import (
        list_project_folder_files,
        read_project_folder_file,
    )

    folder = tmp_path / "notes"
    folder.mkdir()
    (folder / "now.md").write_text("# now\n", encoding="utf-8")
    (folder / "backlog.md").write_text("- item\n", encoding="utf-8")
    nested = folder / "docs"
    nested.mkdir()
    (nested / "readme.md").write_text("hi\n", encoding="utf-8")
    (folder / ".git").mkdir()
    (folder / ".git" / "config").write_text("x", encoding="utf-8")
    (folder / "node_modules").mkdir()
    (folder / "node_modules" / "pkg.js").write_text("x", encoding="utf-8")

    listing = list_project_folder_files(str(folder))
    names = {item.name for item in listing.data}
    assert names == {"now.md", "backlog.md", "readme.md"}
    assert listing.truncated is False
    assert all(item.kind == "document" for item in listing.data)

    content = read_project_folder_file(str(folder), "docs/readme.md")
    assert content.encoding == "text"
    assert content.content == "hi\n"

    with pytest.raises(ValueError, match="Invalid project folder path"):
        read_project_folder_file(str(folder), "../outside.md")

    from agent_server.project_folder_listing import (
        delete_project_folder_file,
        rename_project_folder_file,
    )

    renamed = rename_project_folder_file(str(folder), "now.md", "today.md")
    assert renamed.name == "today.md"
    assert renamed.path == "today.md"
    assert (folder / "today.md").is_file()
    assert not (folder / "now.md").exists()

    delete_project_folder_file(str(folder), "today.md")
    assert not (folder / "today.md").exists()


def test_project_folder_files_http(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    folder = tmp_path / "shared"
    folder.mkdir()
    (folder / "release.md").write_text("ship\n", encoding="utf-8")

    app = create_app(store_path=tmp_path / "agent.db", allowed_hosts=["testserver"])
    with TestClient(app) as client:
        created = client.post(
            "/v1/projects",
            json={"name": "Shared", "folderPath": str(folder)},
        )
        assert created.status_code == 201
        project_id = created.json()["id"]

        listed = client.get(f"/v1/projects/{project_id}/folder-files")
        assert listed.status_code == 200
        body = listed.json()
        assert body["folderPath"] == str(folder.resolve())
        assert [row["name"] for row in body["data"]] == ["release.md"]

        content = client.get(
            f"/v1/projects/{project_id}/folder-files/content",
            params={"path": "release.md"},
        )
        assert content.status_code == 200
        assert content.json()["content"] == "ship\n"

        renamed = client.patch(
            f"/v1/projects/{project_id}/folder-files",
            json={"path": "release.md", "name": "shipped.md"},
        )
        assert renamed.status_code == 200
        assert renamed.json()["name"] == "shipped.md"

        used = client.post(
            f"/v1/projects/{project_id}/folder-files/use-in-chat",
            json={"paths": ["shipped.md"], "title": "Ship notes"},
        )
        assert used.status_code == 201
        used_body = used.json()
        assert used_body["sessionId"]
        assert used_body["paths"] == ["project/shipped.md"]

        deleted = client.delete(
            f"/v1/projects/{project_id}/folder-files",
            params={"path": "shipped.md"},
        )
        assert deleted.status_code == 200
        assert deleted.json()["deleted"] is True
        assert not (folder / "shipped.md").exists()

        bare = client.post("/v1/projects", json={"name": "Bare"})
        assert bare.status_code == 201
        missing = client.get(f"/v1/projects/{bare.json()['id']}/folder-files")
        assert missing.status_code == 404


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
