"""Tests for Modal → host workspace path mirroring."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

from deepagents.backends.protocol import WriteResult

from agent.sandbox_backend.workspace_route import (
    HostWorkspaceMirrorBackend,
    workspace_relative_tool_path,
    wrap_backend_for_host_workspace,
)


def test_workspace_relative_tool_path_variants(tmp_path: Path):
    root = tmp_path / "ws"
    root.mkdir()
    assert workspace_relative_tool_path(str(root / "plans" / "a.md"), root) == (
        "plans/a.md"
    )
    assert workspace_relative_tool_path("/workspace/plans/a.md", root) == "plans/a.md"
    assert workspace_relative_tool_path("plans/a.md", root) == "plans/a.md"
    assert workspace_relative_tool_path("/skills/foo/SKILL.md", root) is None
    assert workspace_relative_tool_path("/tmp/other.md", root) is None


def test_workspace_relative_tool_path_project_symlink(tmp_path: Path):
    import os

    root = tmp_path / "ws"
    root.mkdir()
    linked = tmp_path / "linked"
    linked.mkdir()
    (linked / "backlog.md").write_text("", encoding="utf-8")
    os.symlink(linked, root / "project", target_is_directory=True)

    assert workspace_relative_tool_path(
        str(root / "project" / "backlog.md"), root
    ) == "project/backlog.md"
    assert workspace_relative_tool_path("project/backlog.md", root) == (
        "project/backlog.md"
    )
    # Bare absolute path into the linked folder (bypassing mount) stays rejected.
    assert workspace_relative_tool_path(str(linked / "backlog.md"), root) is None


def test_mirror_write_creates_host_file(tmp_path: Path):
    root = tmp_path / "ws"
    root.mkdir()
    inner = MagicMock()
    inner.write.return_value = WriteResult(path="/workspace/plans/plan.md")
    inner.upload_files = MagicMock()

    backend = HostWorkspaceMirrorBackend(inner, root)
    result = backend.write(str(root / "plans" / "plan.md"), "# Title\n")

    assert result.error is None
    assert Path(result.path).read_text(encoding="utf-8") == "# Title\n"
    assert (root / "plans" / "plan.md").is_file()
    inner.upload_files.assert_called_once()
    uploaded_path, uploaded_bytes = inner.upload_files.call_args[0][0][0]
    assert uploaded_path == "/workspace/plans/plan.md"
    assert uploaded_bytes == b"# Title\n"


def test_wrap_is_idempotent(tmp_path: Path):
    inner = SimpleNamespace(write=MagicMock())
    first = wrap_backend_for_host_workspace(inner, tmp_path)
    second = wrap_backend_for_host_workspace(first, tmp_path)
    assert first is second


def test_mirror_write_overwrites_existing_project_file(tmp_path: Path):
    import os

    root = tmp_path / "ws"
    root.mkdir()
    linked = tmp_path / "linked"
    linked.mkdir()
    (linked / "backlog.md").write_text("old\n", encoding="utf-8")
    os.symlink(linked, root / "project", target_is_directory=True)

    inner = MagicMock()
    inner.upload_files = MagicMock()
    backend = HostWorkspaceMirrorBackend(inner, root)
    result = backend.write(str(root / "project" / "backlog.md"), "- task\n")

    assert result.error is None
    assert (linked / "backlog.md").read_text(encoding="utf-8") == "- task\n"
    uploaded_path, uploaded_bytes = inner.upload_files.call_args[0][0][0]
    assert uploaded_path == "/workspace/project/backlog.md"
    assert uploaded_bytes == b"- task\n"


def test_mirror_read_project_symlink_file(tmp_path: Path):
    """Reading through the project/ symlink must not hit the root-escape check."""
    import os

    from deepagents.backends import FilesystemBackend

    root = tmp_path / "ws"
    root.mkdir()
    linked = tmp_path / "linked"
    linked.mkdir()
    (linked / "backlog.md").write_text("- one\n- two\n", encoding="utf-8")
    os.symlink(linked, root / "project", target_is_directory=True)

    inner = FilesystemBackend(root_dir=str(root), virtual_mode=False)
    backend = HostWorkspaceMirrorBackend(inner, root)
    result = backend.read(str(root / "project" / "backlog.md"))

    assert result.error is None
    assert result.file_data["content"] == "- one\n- two\n"


def test_mirror_awrite_overwrites_existing_project_file(tmp_path: Path):
    """deepagents calls the async variant; it must upsert like sync write."""
    import asyncio
    import os

    from deepagents.backends import FilesystemBackend

    root = tmp_path / "ws"
    root.mkdir()
    linked = tmp_path / "linked"
    linked.mkdir()
    (linked / "backlog.md").write_text("old\n", encoding="utf-8")
    os.symlink(linked, root / "project", target_is_directory=True)

    inner = FilesystemBackend(root_dir=str(root), virtual_mode=False)
    backend = HostWorkspaceMirrorBackend(inner, root)
    result = asyncio.run(
        backend.awrite(str(root / "project" / "backlog.md"), "- task\n")
    )

    assert result.error is None
    assert (linked / "backlog.md").read_text(encoding="utf-8") == "- task\n"


def test_mirror_allows_sandwalk_base_files(tmp_path: Path, monkeypatch):
    """Default policy can read/write/edit anywhere under SANDWALK_CONFIG_DIR."""
    from deepagents.backends import FilesystemBackend

    config = tmp_path / "sandwalk"
    skills = config / "skills" / "boltz" / "references"
    skills.mkdir(parents=True)
    example = skills / "examples.md"
    example.write_text("old\n", encoding="utf-8")
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.setenv("SANDWALK_CONFIG_DIR", str(config))

    inner = FilesystemBackend(root_dir=str(workspace), virtual_mode=False)
    backend = HostWorkspaceMirrorBackend(inner, workspace)

    read = backend.read(str(example))
    assert read.error is None
    assert read.file_data["content"] == "old\n"

    edit = backend.edit(str(example), "old", "new")
    assert edit.error is None
    assert example.read_text(encoding="utf-8") == "new\n"

    created = config / "artifacts" / "result.txt"
    write = backend.write(str(created), "result\n")
    assert write.error is None
    assert created.read_text(encoding="utf-8") == "result\n"


def test_mirror_delete_removes_host_and_is_protocol_visible(tmp_path: Path):
    """deepagents 0.7 probes type(backend).delete — must exist on the class."""
    root = tmp_path / "ws"
    root.mkdir()
    target = root / "plans" / "gone.md"
    target.parent.mkdir(parents=True)
    target.write_text("x\n", encoding="utf-8")

    inner = MagicMock()
    # Prefer a simple namespace result so older deepagents without DeleteResult
    # still exercise the host-delete path.
    inner.delete.return_value = SimpleNamespace(
        path="/workspace/plans/gone.md", error=None
    )
    backend = HostWorkspaceMirrorBackend(inner, root)

    assert hasattr(type(backend), "delete")
    result = backend.delete(str(target))
    assert getattr(result, "error", None) is None
    assert not target.exists()
    inner.delete.assert_called_once_with("/workspace/plans/gone.md")


def test_mirror_backend_survives_deepagents_class_attr_probes(tmp_path: Path):
    """Regression: __getattr__ forwarding is invisible to type(backend).attr.

    deepagents 0.7+ uses ``type(backend).delete is not BackendProtocol.delete``
    (and similar) before filtering tools. If a method only exists via
    ``__getattr__``, that probe raises AttributeError and kills the run.
    """
    from deepagents.backends.protocol import BackendProtocol

    backend = HostWorkspaceMirrorBackend(MagicMock(), tmp_path)
    # Methods deepagents may probe on the class (optional overrides).
    for name in ("delete", "adelete", "write", "edit", "read", "awrite", "aedit", "aread"):
        if not hasattr(BackendProtocol, name):
            continue
        # Must not raise — class attr lookup, not instance __getattr__.
        getattr(type(backend), name)
    supports = getattr(
        __import__("deepagents.backends.protocol", fromlist=["_supports_delete"]),
        "_supports_delete",
        None,
    )
    if callable(supports):
        assert supports(backend) is True
