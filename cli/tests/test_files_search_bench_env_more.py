"""Coverage for file search tools and bench environment snapshots."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from agent_server.bench_service.environment import capture_bench_environment
from tools.files_search import list_directory, search_content, search_files


def test_list_directory_denies_missing_and_lists_bounds(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("tools.files_search._is_within_cwd", lambda _path: False)
    monkeypatch.setattr("tools.files_search._is_allowed", lambda _path, _config: False)
    denied = list_directory("/etc")
    assert denied["error"] == "path_not_allowed"

    monkeypatch.setattr("tools.files_search._is_within_cwd", lambda path: Path(path).exists())
    monkeypatch.setattr("tools.files_search._is_allowed", lambda _path, _config: True)
    missing = list_directory(str(tmp_path / "nope"))
    assert missing["error"] == "file_not_found"

    note = tmp_path / "note.txt"
    note.write_text("hi", encoding="utf-8")
    not_dir = list_directory(str(note))
    assert not_dir["error"] == "not_directory"

    visible = tmp_path / "keep.txt"
    visible.write_text("a", encoding="utf-8")
    hidden = tmp_path / ".secret"
    hidden.write_text("b", encoding="utf-8")
    listed = list_directory(str(tmp_path), show_hidden=False, max_entries=1)
    assert listed["count"] == 1

    shown = list_directory(str(tmp_path), show_hidden=True, max_entries=10)
    assert shown["count"] >= 2


def test_list_directory_skips_outside_links_and_stat_errors(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    link = tmp_path / "outside"
    link.symlink_to("/etc/hosts")
    listed = list_directory(str(tmp_path))
    assert all(item["name"] != "outside" for item in listed["entries"])

    def boom(self):
        def _gen():
            raise RuntimeError("iter")
            yield None

        return _gen()

    monkeypatch.setattr(Path, "iterdir", boom)
    failed = list_directory(str(tmp_path))
    assert failed["error"] == "iter"


def test_search_files_and_content(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("tools.files_search._is_within_cwd", lambda _path: False)
    assert search_files("*.txt", path="/etc")["error"] == "path_not_allowed"
    assert search_content("x", path="/etc")["error"] == "path_not_allowed"

    monkeypatch.setattr("tools.files_search._is_within_cwd", lambda _path: True)
    (tmp_path / "a.txt").write_text("alpha\n" + ("z" * 210), encoding="utf-8")
    (tmp_path / "b.png").write_bytes(b"\x89PNG")
    found = search_files("*.txt")
    assert found["count"] == 1
    assert "a.txt" in found["summary"]

    empty = search_files("*.missing")
    assert empty["count"] == 0

    bad = search_content("(")
    assert "Invalid regex" in bad["summary"]

    hits = search_content("alpha", max_results=1)
    assert hits["matches"][0]["file"].endswith("a.txt")
    long = search_content("z" * 50, max_results=5)
    assert long["matches"][0]["text"].endswith("...")

    huge = tmp_path / "big.txt"
    huge.write_bytes(b"x" * 1_000_001)
    skipped = search_content("x", glob="big.txt")
    assert skipped["count"] == 0


def test_bench_environment_snapshot_and_failures(monkeypatch) -> None:
    monkeypatch.setattr(
        "agent_server.bench_service.environment._sandwalk_version",
        lambda: "0.1.11",
    )
    monkeypatch.setattr(
        "agent_server.bench_service.environment._core_packages",
        lambda: {"deepagents": "1"},
    )
    monkeypatch.setattr(
        "agent_server.bench_service.environment._runtime_settings",
        lambda: {"model": "gpt"},
    )
    monkeypatch.setattr(
        "agent_server.bench_service.environment._sandbox_settings",
        lambda: {"backend": "local"},
    )
    monkeypatch.setattr(
        "agent_server.bench_service.environment._skills_snapshot",
        lambda: [{"name": "sites"}],
    )
    monkeypatch.setattr(
        "agent_server.bench_service.environment._mcp_snapshot",
        lambda deps: [] if deps is None else [{"name": "pymol"}],
    )
    snap = capture_bench_environment(
        SimpleNamespace(),
        model_id="gpt",
        provider="openai",
        specialist_id="bio",
        thinking=True,
        suite_id="s",
        sample_size=2,
        pack_id="p",
        matrix="m",
    )
    assert snap["sandwalk_version"] == "0.1.11"
    assert snap["mcp_servers"][0]["name"] == "pymol"
    assert capture_bench_environment(None, model_id="gpt")["mcp_servers"] == []

    def explode():
        raise RuntimeError("boom")

    monkeypatch.setattr("agent_server.bench_service.environment._sandwalk_version", explode)
    failed = capture_bench_environment(None, model_id="gpt", provider="openai")
    assert failed["error"] == "boom"
    assert failed["model"]["model_id"] == "gpt"
