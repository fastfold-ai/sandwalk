"""Extra workspace service coverage."""

from __future__ import annotations

from pathlib import Path

import pytest

from agent_server.workspace import (
    WorkspaceConflictError,
    WorkspacePathError,
    WorkspaceService,
)


def test_workspace_list_write_read_roundtrip(tmp_path: Path):
    root = tmp_path / "ws"
    root.mkdir()
    service = WorkspaceService(root)
    written = service.write("notes/hello.md", content="# hi\n")
    assert written.path == "notes/hello.md"
    listed = service.list("", recursive=True)
    paths = {item.path for item in listed}
    assert "notes/hello.md" in paths
    content = service.read("notes/hello.md")
    assert "hi" in content.content
    assert content.version == written.version


def test_workspace_rejects_escape(tmp_path: Path):
    root = tmp_path / "ws"
    root.mkdir()
    service = WorkspaceService(root)
    with pytest.raises(WorkspacePathError):
        service.resolve("../outside.txt")


def test_workspace_conflict_on_stale_version(tmp_path: Path):
    root = tmp_path / "ws"
    root.mkdir()
    service = WorkspaceService(root)
    first = service.write("a.txt", content="one")
    service.write("a.txt", content="two")
    with pytest.raises(WorkspaceConflictError):
        service.write("a.txt", content="three", base_version=first.version)


def test_workspace_create_folder_and_upload(tmp_path: Path):
    root = tmp_path / "ws"
    root.mkdir()
    service = WorkspaceService(root)
    folder = service.create_folder("artifacts/fold")
    assert "fold" in folder
    uploaded = service.upload("artifacts/fold/model.cif", b"data_")
    assert uploaded.path.endswith("model.cif")
