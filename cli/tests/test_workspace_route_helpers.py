"""Host-path routing helpers for the workspace mirror backend."""

from __future__ import annotations

from types import SimpleNamespace

from agent.sandbox_backend import workspace_route as route


def test_host_path_read_and_relative(tmp_path, monkeypatch):
    monkeypatch.setenv("SANDWALK_CONFIG_DIR", str(tmp_path))
    host = tmp_path / "workspaces" / "note.txt"
    host.parent.mkdir()
    host.write_text("one\ntwo\n", encoding="utf-8")
    assert route._sandwalk_host_path(str(host)) == host.resolve()
    assert route._sandwalk_host_path("relative") is None
    assert route._sandwalk_host_path("") is None
    monkeypatch.delenv("SANDWALK_CONFIG_DIR")
    assert route._sandwalk_host_path(str(host)) is None

    binary = tmp_path / "blob.bin"
    binary.write_bytes(b"\xff\xfe")
    blob = route._read_host_file(binary, 0, 10)
    assert blob.file_data["encoding"] == "base64"
    empty = tmp_path / "empty.txt"
    empty.write_text("", encoding="utf-8")
    assert route._read_host_file(empty, 0, 10).file_data is not None
    missing = route._read_host_file(tmp_path / "gone.txt", 0, 10)
    assert missing.error
    past = route._read_host_file(host, 50, 10)
    assert "exceeds" in (past.error or "")
    page = route._read_host_file(host, 1, 1)
    assert page.file_data["content"].startswith("two")

    root = tmp_path / "ws"
    root.mkdir()
    assert route.workspace_relative_tool_path("", root) is None
    assert route.workspace_relative_tool_path("/skills/fold", root) is None
    assert route.workspace_relative_tool_path("notes/a.md", root) == "notes/a.md"
    assert route.workspace_relative_tool_path("foo/../../etc", root) is None
    assert route.workspace_relative_tool_path("/workspace/plans/a.md", root) == "plans/a.md"
    assert route.workspace_relative_tool_path("/workspace", root) == ""
    outside = tmp_path / "outside.txt"
    outside.write_text("x")
    assert route.workspace_relative_tool_path(str(outside), root) is None

    mirrored = route._mirror_host_text(root, "plans/a.md", "body")
    assert mirrored.read_text() == "body"
    assert route._host_abs(root, "plans/a.md").endswith("plans/a.md")
    assert route._modal_path("plans/a.md") == "/workspace/plans/a.md"

    class _Inner:
        def upload_files(self, pairs):
            raise RuntimeError("upload")

        def write(self, path, content):
            return SimpleNamespace(error="exists")

    route._mirror_modal_text(_Inner(), "plans/a.md", "body")
    route._mirror_modal_delete(SimpleNamespace(delete=lambda path: SimpleNamespace(error="missing")), "plans/a.md")

    def _boom(path):
        raise RuntimeError("delete")

    route._mirror_modal_delete(SimpleNamespace(delete=_boom), "plans/a.md")
    route._mirror_modal_delete(SimpleNamespace(), "plans/a.md")

    deleted = route._delete_host_path(mirrored, "plans/a.md")
    assert deleted.path
    folder = root / "dir"
    folder.mkdir()
    (folder / "child").write_text("c")
    assert route._delete_host_path(folder, "dir").path
    missing_del = route._delete_host_path(root / "nope", "nope")
    assert missing_del.error
