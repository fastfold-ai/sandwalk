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


def test_workspace_list_is_bounded_on_huge_trees(tmp_path: Path, monkeypatch):
    """A home-directory-sized workspace must return quickly and partially."""
    import time

    from agent_server.workspace import read_mixin

    root = tmp_path / "ws"
    root.mkdir()
    # 40 dirs x 200 files = 8,000 entries, above the cap.
    for d in range(40):
        folder = root / f"d{d:02d}"
        folder.mkdir()
        for f in range(200):
            (folder / f"f{f:03d}.txt").write_text("x", encoding="utf-8")
    monkeypatch.setattr(read_mixin, "_LIST_MAX_ENTRIES", 1_000)

    started = time.monotonic()
    items = WorkspaceService(root).list("", recursive=True)
    elapsed = time.monotonic() - started
    assert len(items) <= 1_000
    assert elapsed < read_mixin._LIST_TIME_BUDGET_S + 1.0
    # Breadth-first: the top-level folders all made it in before the cap hit.
    assert {i.path for i in items if i.type == "directory"} >= {f"d{d:02d}" for d in range(40)}


def test_workspace_list_skips_noise_dirs_and_does_not_follow_foreign_symlinks(tmp_path: Path):
    import os

    root = tmp_path / "ws"
    root.mkdir()
    (root / "node_modules").mkdir()
    (root / "node_modules" / "big.js").write_text("", encoding="utf-8")
    (root / "src").mkdir()
    (root / "src" / "a.py").write_text("", encoding="utf-8")
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    (elsewhere / "secret.txt").write_text("", encoding="utf-8")
    os.symlink(elsewhere, root / "escape", target_is_directory=True)

    paths = {i.path for i in WorkspaceService(root).list("", recursive=True)}
    assert "src/a.py" in paths
    assert not any(p.startswith("node_modules") for p in paths)
    # The symlink itself is listed, its target is not descended into.
    assert "escape" in paths
    assert "escape/secret.txt" not in paths


def test_workspace_lists_and_reads_project_symlink(tmp_path: Path):
    """Files panel must follow workspace/project → linked folder."""
    import os

    root = tmp_path / "ws"
    root.mkdir()
    linked = tmp_path / "linked"
    linked.mkdir()
    (linked / "README.md").write_text("# plan\n", encoding="utf-8")
    (linked / "notes").mkdir()
    (linked / "notes" / "a.md").write_text("a\n", encoding="utf-8")
    os.symlink(linked, root / "project", target_is_directory=True)

    service = WorkspaceService(root)
    paths = {item.path for item in service.list("", recursive=True)}
    assert "project" in paths or "project/README.md" in paths
    assert "project/README.md" in paths
    assert "project/notes/a.md" in paths

    content = service.read("project/README.md")
    assert "plan" in content.content
    written = service.write("project/README.md", content="# updated\n")
    assert written.path == "project/README.md"
    assert (linked / "README.md").read_text(encoding="utf-8") == "# updated\n"
