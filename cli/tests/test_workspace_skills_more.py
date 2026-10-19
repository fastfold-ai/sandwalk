"""Extra coverage for workspace mirroring and git/archive/npx skill installs.

Subprocess and HTTP are mocked. These tests do not clone repositories or call GitHub.
"""

from __future__ import annotations

import asyncio
import builtins
import io
import json
import os
import subprocess
import zipfile
from pathlib import Path
from types import SimpleNamespace

import httpx
from deepagents.backends import FilesystemBackend
from deepagents.backends.protocol import EditResult, ReadResult, WriteResult

from agent.sandbox_backend import workspace_route as route
from agent.skills import install as skills

_HTTP: dict[str, object] = {"handler": None}


class _HttpClient:
    def __init__(self, *args, **kwargs):
        self.kwargs = kwargs

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def get(self, url, headers=None):
        handler = _HTTP["handler"]
        assert handler is not None
        return handler(url, headers)


def _patch_http(monkeypatch, handler) -> None:
    _HTTP["handler"] = handler
    monkeypatch.setattr(httpx, "Client", _HttpClient)


def _response(url: str, status: int = 200, *, content: bytes | None = None, payload=None):
    kwargs = {}
    if content is not None:
        kwargs["content"] = content
    if payload is not None:
        kwargs["json"] = payload
    return httpx.Response(status, request=httpx.Request("GET", url), **kwargs)


def _zip_bytes(files: dict[str, str]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, text in files.items():
            archive.writestr(name, text)
    return buffer.getvalue()


def _no_release(url, headers=None):
    if "releases/latest" in url:
        return _response(url, 404)
    raise AssertionError(url)


def _release(tag: str):
    def handler(url, headers=None):
        if "releases/latest" in url:
            return _response(
                url,
                payload={"tag_name": tag, "published_at": "2024-05-01T00:00:00Z"},
            )
        raise AssertionError(url)

    return handler


def _plant_skill(dest: Path, *parts: str) -> None:
    skill = dest.joinpath(*parts) if parts else dest
    skill.mkdir(parents=True, exist_ok=True)
    (skill / "SKILL.md").write_text("# skill\n", encoding="utf-8")


# ─── skills install ─────────────────────────────────────────────────────────


def test_git_and_npx_availability(monkeypatch):
    def which_git(name):
        return "/usr/bin/git" if name == "git" else None

    monkeypatch.setattr(skills.shutil, "which", which_git)
    assert skills._git_available() is True
    assert skills._npx_available() is False

    def which_npx(name):
        return "/usr/bin/npx" if name == "npx" else None

    monkeypatch.setattr(skills.shutil, "which", which_npx)
    assert skills._git_available() is False
    assert skills._npx_available() is True


def test_git_clone_branch_sha_and_rev_parse_failures(tmp_path, monkeypatch):
    calls: list[list[str]] = []
    state = {"mode": "sha"}

    def fake_run(cmd, **kwargs):
        calls.append(list(cmd))
        assert kwargs["stdin"] is subprocess.DEVNULL
        assert kwargs["env"]["GIT_TERMINAL_PROMPT"] == "0"
        assert kwargs["env"]["GIT_ASKPASS"] == "echo"
        if cmd[1] == "clone":
            Path(cmd[-1]).mkdir(parents=True)
            return subprocess.CompletedProcess(cmd, 0, "", "")
        if state["mode"] == "sha":
            return subprocess.CompletedProcess(cmd, 0, "deadbeef\n", "")
        if state["mode"] == "blank":
            return subprocess.CompletedProcess(cmd, 0, "   \n", "")
        raise RuntimeError("rev-parse failed")

    monkeypatch.setattr(skills.subprocess, "run", fake_run)
    dest = tmp_path / "repo"
    sha = skills._git_clone("https://github.com/acme/fold.git", "v1", dest)
    assert sha == "deadbeef"
    assert calls[0][:6] == ["git", "clone", "--depth", "1", "--branch", "v1"]
    assert calls[0][-2] == "https://github.com/acme/fold.git"

    state["mode"] = "blank"
    calls.clear()
    bare = tmp_path / "bare"
    assert skills._git_clone("https://github.com/acme/fold.git", None, bare) is None
    assert "--branch" not in calls[0]

    state["mode"] = "boom"
    broken = tmp_path / "broken"
    assert skills._git_clone("https://github.com/acme/fold.git", None, broken) is None


def test_npx_target_edges():
    assert skills._npx_target("") == ("", None, True)
    target, name, whole = skills._npx_target("https://github.com/acme/fold.git")
    assert target.startswith("https://") and name is None and whole is True
    target, name, whole = skills._npx_target("git@github.com:acme/fold.git")
    assert target.startswith("git@") and name is None and whole is True
    assert skills._npx_target("acme/fold@") == ("acme/fold", None, False)
    assert skills._npx_target("acme/fold@skills/binder/") == ("acme/fold", "binder", False)


def test_npx_add_and_update(tmp_path, monkeypatch):
    root = tmp_path / "npx-root"
    skills_dir = tmp_path / "npx-skills"
    monkeypatch.setattr(skills._skills, "NPX_INSTALL_ROOT", root)
    monkeypatch.setattr(skills._skills, "NPX_SKILLS_DIR", skills_dir)
    monkeypatch.setattr(skills._skills, "_npx_available", lambda: True)
    seen: list[tuple[list[str], str]] = []

    def fake_run(cmd, **kwargs):
        seen.append((list(cmd), kwargs["cwd"]))
        assert kwargs["stdin"] is subprocess.DEVNULL
        assert kwargs["timeout"] == skills._CLONE_TIMEOUT_S
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(skills.subprocess, "run", fake_run)

    named = skills.npx_add("acme/fold", ["binder", "dock"])
    whole = skills.npx_add("acme/fold", whole=True)
    plain = skills.npx_add("https://github.com/acme/fold")
    updated = skills._npx_update()

    assert named["ok"] is True and "binder, dock" in named["summary"]
    assert str(skills_dir) in named["summary"]
    assert whole["ok"] is True and "(all)" in whole["summary"]
    assert plain["ok"] is True and "skills:" not in plain["summary"] and "(all)" not in plain["summary"]
    assert updated == {"ok": True, "summary": "Updated npx-installed skills."}
    assert seen[0][0][-4:] == ["--skill", "binder", "--skill", "dock"]
    assert seen[1][0][-2:] == ["--skill", "*"]
    assert "--skill" not in seen[2][0]
    assert seen[3][0] == ["npx", "-y", "skills", "update", "-y"]
    assert seen[0][1] == str(root)
    assert root.is_dir()

    def time_out(cmd, **kwargs):
        raise subprocess.TimeoutExpired(cmd, 120)

    monkeypatch.setattr(skills.subprocess, "run", time_out)
    timed = skills.npx_add("acme/fold", ["binder"])
    assert timed["ok"] is False and "timed out" in timed["summary"]

    def fail(cmd, **kwargs):
        raise RuntimeError("npx boom")

    monkeypatch.setattr(skills.subprocess, "run", fail)
    failed = skills.npx_add("acme/fold")
    assert failed["ok"] is False and "npx boom" in failed["summary"]
    update_failed = skills._npx_update()
    assert update_failed["ok"] is False and "npx boom" in update_failed["summary"]

    monkeypatch.setattr(skills._skills, "_npx_available", lambda: False)
    missing = skills.npx_add("acme/fold")
    assert missing == {"ok": False, "summary": "npx is not available.", "via": "npx"}
    assert skills._npx_update()["summary"] == "npx is not available."

    installed = skills._npx_install("acme/fold@skills/binder")
    assert installed["ok"] is False


def test_download_github_archive_layouts_and_http_errors(tmp_path, monkeypatch):
    def handler(url, headers=None):
        assert url == "https://codeload.github.com/acme/fold/zip/v1"
        return _response(
            url,
            content=_zip_bytes({"fold-v1/binder/SKILL.md": "# binder\n", "fold-v1/README.md": "hi"}),
        )

    _patch_http(monkeypatch, handler)
    root = skills._download_github_archive("acme", "fold", "v1", tmp_path / "one")
    assert root.name == "fold-v1"
    assert (root / "binder" / "SKILL.md").is_file()

    def head(url, headers=None):
        assert url.endswith("/acme/fold/zip/HEAD")
        return _response(url, content=_zip_bytes({"a/SKILL.md": "a", "b/SKILL.md": "b"}))

    _patch_http(monkeypatch, head)
    parent = tmp_path / "many"
    assert skills._download_github_archive("acme", "fold", None, parent) == parent

    def files_only(url, headers=None):
        return _response(url, content=_zip_bytes({"README.md": "x"}))

    _patch_http(monkeypatch, files_only)
    try:
        skills._download_github_archive("acme", "fold", None, tmp_path / "files")
    except RuntimeError as exc:
        assert "no directories" in str(exc)
    else:
        raise AssertionError("expected missing directories")

    def missing(url, headers=None):
        return _response(url, 404)

    _patch_http(monkeypatch, missing)
    try:
        skills._download_github_archive("acme", "fold", None, tmp_path / "http")
    except RuntimeError as exc:
        assert "HTTP 404" in str(exc)
    else:
        raise AssertionError("expected HTTP status failure")

    def offline(url, headers=None):
        raise httpx.ConnectError("offline")

    _patch_http(monkeypatch, offline)
    try:
        skills._download_github_archive("acme", "fold", "main", tmp_path / "net")
    except RuntimeError as exc:
        assert "offline" in str(exc)
    else:
        raise AssertionError("expected connection failure")


def test_resolve_skill_dirs_and_manifest_edges(tmp_path):
    pack = tmp_path / "pack"
    (pack / "alpha").mkdir(parents=True)
    (pack / "beta").mkdir()
    (pack / "alpha" / "SKILL.md").write_text("# a\n", encoding="utf-8")
    (pack / "beta" / "SKILL.md").write_text("# b\n", encoding="utf-8")
    assert [path.name for path in skills._resolve_skill_dirs(pack, None)] == ["alpha", "beta"]

    direct = tmp_path / "direct"
    direct.mkdir()
    (direct / "SKILL.md").write_text("# root\n", encoding="utf-8")
    assert skills._resolve_skill_dirs(direct, "missing/sub") == [direct]

    nested = tmp_path / "nested"
    shallow = nested / "nested" / "pkg" / "my-skill"
    deep = nested / "other" / "deep" / "my_skill"
    shallow.mkdir(parents=True)
    deep.mkdir(parents=True)
    (shallow / "SKILL.md").write_text("# s\n", encoding="utf-8")
    (deep / "SKILL.md").write_text("# d\n", encoding="utf-8")
    (nested / "docs").mkdir()
    found = skills._resolve_skill_dirs(nested, "wanted/my-skill")
    assert found == [shallow]

    assert skills._resolve_skill_dirs(nested, "missing-name") == []
    lone = tmp_path / "file.txt"
    lone.write_text("x", encoding="utf-8")
    assert skills._resolve_skill_dirs(lone, None) == []

    assert skills._read_manifest(tmp_path / "absent")["skills"] == {}
    dest = tmp_path / "manifest"
    dest.mkdir()
    manifest_path = dest / skills._skills.MANIFEST_FILENAME
    manifest_path.write_text("{", encoding="utf-8")
    assert skills._read_manifest(dest) == {"version": 1, "skills": {}}
    manifest_path.write_text('{"version": 1}', encoding="utf-8")
    loaded = skills._read_manifest(dest)
    assert loaded["skills"] == {}
    skills._write_manifest(dest, {"version": 1, "skills": {"binder": {"source": "x"}}})
    assert skills._read_manifest(dest)["skills"]["binder"]["source"] == "x"


def test_local_archive_edges(tmp_path):
    dest = tmp_path / "dest"
    dest.mkdir()
    slip = tmp_path / "slip.zip"
    with zipfile.ZipFile(slip, "w") as archive:
        archive.writestr("../evil.txt", "pwn")
    rejected = skills._install_local_archive(slip, dest)
    assert rejected["ok"] is False
    assert "invalid" in rejected["summary"]

    broken = tmp_path / "broken.zip"
    broken.write_bytes(b"not a zip")
    invalid = skills._install_local_archive(broken, dest)
    assert invalid["ok"] is False
    assert "not a valid" in invalid["summary"]

    empty = tmp_path / "empty.zip"
    with zipfile.ZipFile(empty, "w") as archive:
        archive.writestr("README.md", "hi")
    missing = skills._install_local_archive(empty, dest)
    assert missing["ok"] is False
    assert "No SKILL.md" in missing["summary"]

    nested = tmp_path / "nested.zip"
    with zipfile.ZipFile(nested, "w") as archive:
        archive.writestr("repo-main/binder/SKILL.md", "# binder\n")
    installed = skills._install_local_archive(nested, dest, manifest_source="custom")
    assert installed["ok"] is True and installed["via"] == "local-archive"
    saved = json.loads((dest / skills._skills.MANIFEST_FILENAME).read_text(encoding="utf-8"))
    assert saved["skills"]["binder"]["source"] == "custom"

    folder = tmp_path / "folder-skill"
    folder.mkdir()
    (folder / "SKILL.md").write_text("# folder\n", encoding="utf-8")
    local = skills._install_local(str(folder), dest, manifest_source="  custom  ")
    assert local["ok"] is True
    saved = json.loads((dest / skills._skills.MANIFEST_FILENAME).read_text(encoding="utf-8"))
    assert saved["skills"]["folder-skill"]["source"] == "custom"


def _patch_tools(monkeypatch, *, git: bool, npx: bool) -> None:
    monkeypatch.setattr(skills._skills, "_git_available", lambda: git)
    monkeypatch.setattr(skills._skills, "_npx_available", lambda: npx)


def test_install_github_source_git_archive_and_npx(tmp_path, monkeypatch):
    dest = tmp_path / "dest"
    monkeypatch.setattr(skills._skills, "NPX_INSTALL_ROOT", tmp_path / "npx-root")
    monkeypatch.setattr(skills._skills, "NPX_SKILLS_DIR", tmp_path / "npx-skills")
    _patch_tools(monkeypatch, git=True, npx=False)

    def empty_clone(cmd, **kwargs):
        if cmd[1] == "clone":
            Path(cmd[-1]).mkdir(parents=True)
            return subprocess.CompletedProcess(cmd, 0, "", "")
        return subprocess.CompletedProcess(cmd, 0, "abc\n", "")

    monkeypatch.setattr(skills.subprocess, "run", empty_clone)
    empty = skills._install_github_source(
        "acme/fold",
        "https://github.com/acme/fold.git",
        None,
        None,
        dest,
        None,
    )
    assert empty["ok"] is False and empty["via"] == "git" and "No SKILL.md" in empty["summary"]

    def clone_auth_error(cmd, **kwargs):
        raise subprocess.CalledProcessError(128, cmd, stderr="x" * 250)

    monkeypatch.setattr(skills.subprocess, "run", clone_auth_error)

    def archive_ok(url, headers=None):
        return _response(
            url,
            content=_zip_bytes({"fold-main/binder/SKILL.md": "# binder\n"}),
        )

    _patch_http(monkeypatch, archive_ok)
    archived = skills._install_github_source(
        "acme/fold",
        "https://github.com/acme/fold.git",
        "main",
        None,
        dest,
        "v9",
    )
    assert archived["ok"] is True and archived["via"] == "archive"
    assert archived["installed"] == ["binder"]

    def clone_times_out(cmd, **kwargs):
        if cmd[0] == "git":
            raise subprocess.TimeoutExpired(cmd, 1)
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(skills.subprocess, "run", clone_times_out)
    _patch_tools(monkeypatch, git=True, npx=True)

    def archive_offline(url, headers=None):
        raise httpx.ConnectError("offline")

    _patch_http(monkeypatch, archive_offline)
    via_npx = skills._install_github_source(
        "acme/fold@binder",
        "https://github.com/acme/fold.git",
        None,
        "binder",
        dest,
        None,
    )
    assert via_npx["ok"] is True and via_npx["via"] == "npx"

    def everything_fails(cmd, **kwargs):
        if cmd[0] == "git":
            raise subprocess.CalledProcessError(128, cmd, stderr="fatal: auth")
        raise RuntimeError("npx broke")

    monkeypatch.setattr(skills.subprocess, "run", everything_fails)

    def archive_status(url, headers=None):
        return _response(url, 503)

    _patch_http(monkeypatch, archive_status)
    failed = skills._install_github_source(
        "acme/fold",
        "https://github.com/acme/fold.git",
        None,
        None,
        dest,
        None,
    )
    assert failed["ok"] is False and failed["via"] == "git"
    assert "fatal: auth" in failed["summary"]
    assert "HTTP 503" in failed["summary"]
    assert "npx broke" in failed["summary"]
    assert ";" in failed["summary"]

    _patch_tools(monkeypatch, git=True, npx=False)
    gitlab = skills._install_github_source(
        "https://gitlab.com/acme/fold.git",
        "https://gitlab.com/acme/fold.git",
        None,
        None,
        dest,
        None,
    )
    assert gitlab["ok"] is False
    assert "fatal: auth" in gitlab["summary"]
    assert ";" not in gitlab["summary"]

    _patch_tools(monkeypatch, git=False, npx=False)
    nothing = skills._install_github_source(
        "https://gitlab.com/acme/fold.git",
        "https://gitlab.com/acme/fold.git",
        None,
        None,
        dest,
        None,
    )
    assert nothing["summary"] == "Could not install skill from GitHub."

    _patch_tools(monkeypatch, git=False, npx=True)

    def npx_only(cmd, **kwargs):
        assert cmd[0] == "npx"
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr(skills.subprocess, "run", npx_only)
    skipped_archive = skills._install_github_source(
        "https://gitlab.com/acme/fold.git",
        "https://gitlab.com/acme/fold.git",
        None,
        None,
        dest,
        None,
    )
    assert skipped_archive["ok"] is True and skipped_archive["via"] == "npx"


def test_install_skill_github_branches(tmp_path, monkeypatch):
    dest = tmp_path / "dest"
    monkeypatch.setattr(skills._skills, "GLOBAL_SKILLS_DIR", tmp_path / "global")
    monkeypatch.setattr(skills._skills, "NPX_INSTALL_ROOT", tmp_path / "npx-root")
    monkeypatch.setattr(skills._skills, "NPX_SKILLS_DIR", tmp_path / "npx-skills")
    _patch_tools(monkeypatch, git=True, npx=True)
    calls: list[list[str]] = []

    def fake_run(cmd, **kwargs):
        calls.append(list(cmd))
        if cmd[0] == "npx":
            if fake_run.fail_npx:
                raise subprocess.CalledProcessError(1, cmd, stderr="npx no")
            return subprocess.CompletedProcess(cmd, 0, "", "")
        if cmd[1] == "clone":
            _plant_skill(Path(cmd[-1]), "skills", "binder")
            return subprocess.CompletedProcess(cmd, 0, "", "")
        return subprocess.CompletedProcess(cmd, 0, "cafebabe\n", "")

    fake_run.fail_npx = False
    monkeypatch.setattr(skills.subprocess, "run", fake_run)
    _patch_http(monkeypatch, _release("v3.1.0"))

    prefer = skills.install_skill("acme/fold@skills/binder", dest=dest, prefer_npx=True)
    assert prefer["ok"] is True and prefer["via"] == "npx"
    assert calls[0][0] == "npx"
    assert "v3.1.0" not in calls[0]

    calls.clear()
    fake_run.fail_npx = True
    fallback = skills.install_skill("acme/fold@skills/binder", dest=dest, prefer_npx=True)
    assert fallback["ok"] is True and fallback["via"] == "git"
    clone = next(cmd for cmd in calls if "clone" in cmd)
    assert "--branch" in clone and "v3.1.0" in clone
    manifest = json.loads((dest / skills._skills.MANIFEST_FILENAME).read_text(encoding="utf-8"))
    assert manifest["skills"]["binder"]["release"] == "v3.1.0"
    assert manifest["skills"]["binder"]["commit"] == "cafebabe"

    calls.clear()
    fake_run.fail_npx = False
    _patch_tools(monkeypatch, git=True, npx=False)
    pinned = skills.install_skill(
        "https://github.com/acme/fold/tree/main/skills/binder",
        dest=dest,
    )
    assert pinned["ok"] is True and pinned["via"] == "git"
    clone = next(cmd for cmd in calls if "clone" in cmd)
    assert "main" in clone and "v3.1.0" not in clone

    calls.clear()
    _patch_http(monkeypatch, _no_release)

    def resolve_name(name):
        assert name == "fold"
        return "acme/fold"

    monkeypatch.setattr(skills._skills, "_resolve_name_to_source", resolve_name)

    def clone_root_skill(cmd, **kwargs):
        calls.append(list(cmd))
        if cmd[1] == "clone":
            _plant_skill(Path(cmd[-1]))
            return subprocess.CompletedProcess(cmd, 0, "", "")
        return subprocess.CompletedProcess(cmd, 0, "\n", "")

    monkeypatch.setattr(skills.subprocess, "run", clone_root_skill)
    named = skills.install_skill("fold", dest=dest)
    assert named["ok"] is True and named["installed"] == ["repo"]
    clone = next(cmd for cmd in calls if "clone" in cmd)
    assert "--branch" not in clone

    default_dest = tmp_path / "global"
    calls.clear()
    defaulted = skills.install_skill("acme/fold")
    assert defaulted["ok"] is True
    assert (default_dest / "repo" / "SKILL.md").is_file()


# ─── workspace route ────────────────────────────────────────────────────────


def test_host_path_relative_and_modal_edges(tmp_path, monkeypatch):
    base = tmp_path / "cfg"
    base.mkdir()
    monkeypatch.setenv("SANDWALK_CONFIG_DIR", str(base))
    assert route._sandwalk_host_path(str(base)) == base.resolve()
    outside = tmp_path / "outside.txt"
    outside.write_text("z", encoding="utf-8")
    assert route._sandwalk_host_path(str(outside)) is None

    real_resolve = Path.resolve

    def explode(self, *args, **kwargs):
        if self.name == "explode":
            raise OSError("symlink loop")
        return real_resolve(self, *args, **kwargs)

    monkeypatch.setattr(Path, "resolve", explode)
    assert route._sandwalk_host_path(str(base / "explode" / "file.txt")) is None

    root = tmp_path / "ws"
    root.mkdir()
    monkeypatch.delenv("SANDWALK_CONFIG_DIR", raising=False)
    assert route.workspace_relative_tool_path(".", root) is None
    assert route.workspace_relative_tool_path("./", root) is None
    assert route._host_abs(root, "") == str(root)
    assert route._modal_path("") == "/workspace"

    def boom(path, workspace):
        raise RuntimeError("unreadable")

    monkeypatch.setattr(
        "agent_server.project_folder.path_under_workspace_or_project",
        boom,
    )
    assert route.workspace_relative_tool_path("/var/tmp/file.txt", root) is None


def test_mirror_modal_failure_modes(tmp_path, monkeypatch):
    class BoomFS(FilesystemBackend):
        def upload_files(self, files):
            raise RuntimeError("upload")

        def write(self, path, content):
            raise AssertionError("filesystem backend should not be written")

    route._mirror_modal_text(
        BoomFS(root_dir=str(tmp_path), virtual_mode=False),
        "a.md",
        "hi",
    )

    writes: list[str] = []

    class Inner:
        def upload_files(self, files):
            raise RuntimeError("upload")

        def write(self, path, content):
            writes.append(path)
            if len(writes) == 1:
                raise RuntimeError("write")
            return SimpleNamespace(error="exists")

    real_import = builtins.__import__

    def block_backends(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "deepagents.backends":
            raise ImportError("blocked")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", block_backends)
    route._mirror_modal_text(Inner(), "a.md", "x")
    route._mirror_modal_text(Inner(), "b.md", "y")
    assert writes == ["/workspace/a.md", "/workspace/b.md"]


def test_delete_host_fifo_and_oserror(tmp_path, monkeypatch):
    fifo = tmp_path / "pipe"
    os.mkfifo(fifo)
    deleted = route._delete_host_path(fifo, "pipe")
    assert deleted.error is None
    assert not fifo.exists()

    target = tmp_path / "real.md"
    target.write_text("keep", encoding="utf-8")
    link = tmp_path / "alias.md"
    link.symlink_to(target)
    assert route._delete_host_path(link, "alias.md").error is None
    assert not link.exists()
    assert target.read_text(encoding="utf-8") == "keep"

    locked = tmp_path / "locked.md"
    locked.write_text("x", encoding="utf-8")
    real_unlink = Path.unlink

    def fail_unlink(self, *args, **kwargs):
        if self.name == "locked.md":
            raise OSError("busy")
        return real_unlink(self, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", fail_unlink)
    failed = route._delete_host_path(locked, "locked.md")
    assert failed.error and "busy" in failed.error


def _workspace(tmp_path: Path) -> tuple[Path, route.HostWorkspaceMirrorBackend, SimpleNamespace]:
    root = tmp_path / "ws"
    root.mkdir()
    inner = SimpleNamespace()
    backend = route.HostWorkspaceMirrorBackend(inner, root)
    return root, backend, inner


def test_backend_write_read_and_forward(tmp_path, monkeypatch):
    monkeypatch.delenv("SANDWALK_CONFIG_DIR", raising=False)
    root, backend, inner = _workspace(tmp_path)
    inner.write = lambda file_path, content: WriteResult(error="rejected")
    inner.read = lambda file_path, offset=0, limit=2000: ReadResult(error=f"inner:{file_path}:{offset}")

    rejected = backend.write("/tmp/not-ours.txt", "data")
    assert rejected.error == "rejected"
    assert backend.read("/tmp/not-ours.txt", offset=2, limit=3).error == "inner:/tmp/not-ours.txt:2"

    (root / "plans").mkdir()
    write_error = backend.write("plans", "x")
    assert write_error.error and "Error writing" in write_error.error
    workspace_write = backend.write("/workspace", "root")
    assert workspace_write.error and "Error writing" in workspace_write.error

    missing = backend.read("missing.md", offset=1, limit=4)
    assert missing.error == "inner:/workspace/missing.md:1"
    inner.label = "forwarded"
    assert backend.label == "forwarded"

    config = tmp_path / "cfg"
    config.mkdir()
    monkeypatch.setenv("SANDWALK_CONFIG_DIR", str(config))
    folder = config / "subdir"
    folder.mkdir()
    host_write = backend.write(str(folder), "nope")
    assert host_write.error and "Error writing" in host_write.error
    folder_read = backend.read(str(folder))
    assert folder_read.error and "inner:" in folder_read.error


def test_backend_edit_workspace_and_host(tmp_path, monkeypatch):
    monkeypatch.delenv("SANDWALK_CONFIG_DIR", raising=False)
    root, backend, inner = _workspace(tmp_path)
    uploads: list[str] = []
    state = {"error": "modal-miss"}

    def edit(file_path, old_string, new_string, replace_all=False):
        state["path"] = file_path
        state["replace_all"] = replace_all
        if state["error"]:
            return EditResult(error=state["error"])
        return EditResult(path=file_path, occurrences=4)

    def upload(files):
        uploads.append(files[0][0])

    inner.edit = edit
    inner.upload_files = upload

    modal_error = backend.edit("missing.md", "a", "b")
    assert modal_error.error == "modal-miss"
    assert state["path"] == "/workspace/missing.md"
    state["error"] = None
    modal_ok = backend.edit("/workspace", "a", "b", replace_all=True)
    assert modal_ok.error is None
    assert modal_ok.occurrences == 4
    assert modal_ok.path == str(root)

    note = root / "notes.md"
    note.write_text("alpha alpha\n", encoding="utf-8")
    missing_text = backend.edit("notes.md", "nope", "x")
    assert missing_text.error and "not found" in missing_text.error
    many = backend.edit("notes.md", "alpha", "beta")
    assert many.error and "replace_all" in many.error
    replaced = backend.edit(str(root / "notes.md"), "alpha", "beta", replace_all=True)
    assert replaced.error is None and replaced.occurrences == 2
    assert note.read_text(encoding="utf-8") == "beta beta\n"
    assert uploads[-1] == "/workspace/notes.md"

    real_read = Path.read_text

    def fail_read(self, *args, **kwargs):
        if self.name == "notes.md":
            raise OSError("denied")
        return real_read(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", fail_read)
    read_error = backend.edit("notes.md", "beta", "gamma")
    assert read_error.error and "reading" in read_error.error
    monkeypatch.setattr(Path, "read_text", real_read)

    real_write = Path.write_text

    def fail_write(self, *args, **kwargs):
        if self.name in {"notes.md", "host.md"}:
            raise OSError("full")
        return real_write(self, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", fail_write)
    write_error = backend.edit("notes.md", "beta beta", "gamma")
    assert write_error.error and "writing" in write_error.error

    monkeypatch.setattr(Path, "write_text", real_write)
    config = tmp_path / "cfg"
    host = config / "host.md"
    host.parent.mkdir()
    host.write_text("one one\n", encoding="utf-8")
    monkeypatch.setenv("SANDWALK_CONFIG_DIR", str(config))
    assert backend.edit(str(host), "missing", "x").error
    assert "replace_all" in (backend.edit(str(host), "one", "two").error or "")
    replaced_host = backend.edit(str(host), "one", "two", replace_all=True)
    assert replaced_host.occurrences == 2
    assert host.read_text(encoding="utf-8") == "two two\n"

    monkeypatch.setattr(Path, "read_text", fail_read)
    host_named = config / "notes.md"
    host_named.write_text("body\n", encoding="utf-8")
    assert "reading" in (backend.edit(str(host_named), "body", "x").error or "")
    monkeypatch.setattr(Path, "read_text", real_read)
    monkeypatch.setattr(Path, "write_text", fail_write)
    assert "writing" in (backend.edit(str(host), "two two", "three").error or "")

    other = config / "subdir"
    other.mkdir()
    inner_edit = backend.edit(str(other), "a", "b")
    assert inner_edit.error is None and state["path"] == str(other)


def test_backend_delete_routes(tmp_path, monkeypatch):
    monkeypatch.delenv("SANDWALK_CONFIG_DIR", raising=False)
    root, backend, inner = _workspace(tmp_path)
    deleted: list[str] = []

    def delete(file_path):
        deleted.append(file_path)
        return SimpleNamespace(error="modal", path=None)

    inner.delete = delete
    missing = backend.delete("ghost.md")
    assert missing.error is None
    assert missing.path == str(root / "ghost.md")
    assert deleted == ["/workspace/ghost.md"]

    locked = root / "locked.md"
    locked.write_text("x", encoding="utf-8")
    real_unlink = Path.unlink

    def fail_unlink(self, *args, **kwargs):
        if self.name == "locked.md":
            raise OSError("busy")
        return real_unlink(self, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", fail_unlink)
    failed = backend.delete("locked.md")
    assert failed.error and "busy" in failed.error
    assert deleted == ["/workspace/ghost.md"]

    bare = route.HostWorkspaceMirrorBackend(SimpleNamespace(), root)
    unsupported = bare.delete("/tmp/not-ours.txt")
    assert unsupported.error and "not supported" in unsupported.error

    config = tmp_path / "cfg"
    host = config / "gone.txt"
    host.parent.mkdir()
    host.write_text("x", encoding="utf-8")
    monkeypatch.setenv("SANDWALK_CONFIG_DIR", str(config))
    monkeypatch.setattr(Path, "unlink", real_unlink)
    removed = backend.delete(str(host))
    assert removed.error is None
    assert not host.exists()

    forwarded = backend.delete("/tmp/not-ours.txt")
    assert forwarded.path is None or forwarded.error == "modal"
    assert deleted[-1] == "/tmp/not-ours.txt"


def test_async_edit_read_and_delete(tmp_path, monkeypatch):
    monkeypatch.delenv("SANDWALK_CONFIG_DIR", raising=False)
    root, backend, inner = _workspace(tmp_path)
    inner.upload_files = lambda files: None
    inner.delete = lambda file_path: SimpleNamespace(error=None, path=file_path)
    note = root / "note.md"
    note.write_text("old\n", encoding="utf-8")

    edited = asyncio.run(backend.aedit("note.md", "old", "new"))
    assert edited.error is None and edited.occurrences == 1
    read = asyncio.run(backend.aread("note.md"))
    assert read.file_data["content"] == "new\n"
    removed = asyncio.run(backend.adelete("note.md"))
    assert removed.error is None
    assert not note.exists()


def test_delete_result_fallback_for_older_deepagents(monkeypatch):
    """Older deepagents builds have no DeleteResult; the module defines its own."""
    import importlib

    real_import = builtins.__import__

    def hide_delete_result(name, globals=None, locals=None, fromlist=(), level=0):
        if (
            name == "deepagents.backends.protocol"
            and fromlist
            and "DeleteResult" in fromlist
        ):
            raise ImportError("deepagents < 0.7")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", hide_delete_result)
    try:
        importlib.reload(route)
        fallback = route.DeleteResult(path="/tmp/gone.md")
        assert fallback.path == "/tmp/gone.md"
        assert fallback.error is None
        assert route.DeleteResult(error="missing").error == "missing"
    finally:
        builtins.__import__ = real_import
        importlib.reload(route)
