"""Unit tests for sandbox sync helpers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from agent.sandbox_sync import (
    iter_local_files,
    local_rel_from_remote,
    pull_tree,
    push_paths,
    push_tree,
    remote_workspace_path,
    seed_skills,
    should_skip_path,
)


@dataclass
class _FakeUpload:
    path: str
    error: str | None = None


@dataclass
class _FakeDownload:
    path: str
    content: bytes | None = None
    error: str | None = None


class FakeBackend:
    def __init__(self) -> None:
        self.files: dict[str, bytes] = {}
        self.commands: list[str] = []

    def upload_files(self, files: list[tuple[str, bytes]]):
        out = []
        for path, content in files:
            self.files[path] = content
            out.append(_FakeUpload(path=path))
        return out

    def download_files(self, paths: list[str]):
        out = []
        for path in paths:
            if path in self.files:
                out.append(_FakeDownload(path=path, content=self.files[path]))
            else:
                out.append(_FakeDownload(path=path, error="file_not_found"))
        return out

    def execute(self, command: str, *, timeout: int | None = None):
        self.commands.append(command)
        if command.startswith("find "):
            listing = "\n".join(sorted(self.files))
            return type("R", (), {"output": listing, "exit_code": 0})()
        return type("R", (), {"output": "", "exit_code": 0})()


def test_should_skip_and_iter(tmp_path: Path):
    (tmp_path / "keep.txt").write_text("a")
    cache = tmp_path / "__pycache__"
    cache.mkdir()
    (cache / "x.pyc").write_text("b")
    (tmp_path / ".DS_Store").write_text("c")
    files = iter_local_files(tmp_path)
    assert [p.name for p in files] == ["keep.txt"]
    assert should_skip_path(cache / "x.pyc", root=tmp_path)


def test_remote_path_helpers():
    assert remote_workspace_path("uploads/a.txt") == "/workspace/uploads/a.txt"
    assert local_rel_from_remote("/workspace/uploads/a.txt") == "uploads/a.txt"
    assert local_rel_from_remote("/skills/foo") is None


def test_push_pull_roundtrip(tmp_path: Path):
    (tmp_path / "hello.txt").write_text("hi")
    backend = FakeBackend()
    assert push_tree(backend, tmp_path) == 1
    assert backend.files["/workspace/hello.txt"] == b"hi"

    out = tmp_path / "out"
    out.mkdir()
    backend.files["/workspace/generated.txt"] = b"bye"
    assert pull_tree(backend, out) == 2
    assert (out / "hello.txt").read_text() == "hi"
    assert (out / "generated.txt").read_text() == "bye"


def test_push_paths_and_seed_skills(tmp_path: Path):
    (tmp_path / "a.txt").write_text("1")
    (tmp_path / "b.txt").write_text("2")
    backend = FakeBackend()
    assert push_paths(backend, tmp_path, ["a.txt", "../etc/passwd", "missing"]) == 1
    assert "/workspace/a.txt" in backend.files
    assert any(cmd.startswith("mkdir -p") for cmd in backend.commands)

    skills = tmp_path / "skills" / "demo"
    skills.mkdir(parents=True)
    (skills / "SKILL.md").write_text("---\nname: demo\n---\n")
    (skills / "scripts").mkdir()
    (skills / "scripts" / "run.py").write_text("print(1)\n")
    n = seed_skills(backend, [tmp_path / "skills"])
    assert n >= 2
    assert "/skills/demo/SKILL.md" in backend.files
    assert any("/skills/demo/scripts" in cmd for cmd in backend.commands)
