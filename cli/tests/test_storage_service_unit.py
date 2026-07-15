"""Additional storage_service coverage."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from agent_server.storage_service import (
    StorageService,
    _path_size_bytes,
    _python_env_category,
)


def test_path_size_bytes_file_and_missing(tmp_path: Path):
    missing = tmp_path / "nope"
    assert _path_size_bytes(missing) == 0

    file_path = tmp_path / "file.bin"
    file_path.write_bytes(b"12345")
    assert _path_size_bytes(file_path) == 5


def test_path_size_bytes_directory_walk(tmp_path: Path):
    nested = tmp_path / "dir" / "sub"
    nested.mkdir(parents=True)
    (nested / "a.txt").write_bytes(b"abc")
    with patch("agent_server.storage_service.subprocess.run", side_effect=OSError("no du")):
        size = _path_size_bytes(tmp_path / "dir")
    assert size == 3


def test_python_env_category_truncates_packages(tmp_path: Path):
    env_root = tmp_path / "venv"
    env_root.mkdir()
    (env_root / "pyvenv.cfg").write_text("home = /usr\n", encoding="utf-8")
    many = [(f"pkg{i}", "1.0") for i in range(500)]
    with (
        patch("agent_server.storage_service.resolve_python_env_root", return_value=env_root),
        patch("agent_server.storage_service._path_size_bytes", return_value=100),
        patch("agent_server.storage_service.list_installed_packages", return_value=many),
    ):
        category = _python_env_category()
    assert category is not None
    assert any(child.id == "python_env:pkg:truncated" for child in category.children)


def test_storage_report_categories_and_other_bucket(tmp_path: Path):
    home = tmp_path / "home"
    home.mkdir()
    (home / "cache").mkdir()
    (home / "cache" / "x.bin").write_bytes(b"x" * 10)
    (home / "skills").mkdir()
    (home / "skills" / "fold").mkdir()
    (home / "sessions").mkdir()
    (home / "extra-bucket").mkdir()
    (home / "extra-bucket" / "orphan.txt").write_bytes(b"yy")

    data_base = home / "data"
    data_base.mkdir()
    (data_base / "depmap").mkdir()
    (data_base / "depmap" / "file.csv").write_bytes(b"csv")

    with (
        patch("agent_server.storage_service.Config.load") as load_cfg,
        patch("agent_server.storage_service._python_env_category", return_value=None),
        patch("agent_server.storage_service.shutil.disk_usage") as disk_usage,
    ):
        cfg = load_cfg.return_value
        cfg.get.return_value = str(data_base)
        disk_usage.return_value = type("DU", (), {"free": 999})()

        report = StorageService().get_report(home=home)

    ids = {item.id for item in report.categories}
    assert "cache" in ids
    assert "datasets" in ids
    assert "sessions" in ids
    assert "other" in ids
    assert report.location.path == str(home)
    assert report.total_bytes > 0
    assert report.available_bytes == 999

    sessions = next(item for item in report.categories if item.id == "sessions")
    assert sessions.path is not None
    assert "sessions" in sessions.path
    assert "(+" in sessions.path
    assert sessions.children
    assert any(child.path and "agent-server.db" in child.path for child in sessions.children)
    assert report.database is not None
    assert report.database.path.endswith("agent-server.db")


def test_probe_agent_database_healthy(tmp_path: Path):
    from agent_server.store import AgentStore
    from agent_server.storage_service import probe_agent_database

    home = tmp_path / "home"
    home.mkdir()
    store = AgentStore(home / "agent-server.db", exclusive=True)
    store.create_session(title="probe", workspace_path=None)
    store.close()

    probe = probe_agent_database(home)
    assert probe.exists
    assert probe.integrity == "ok"
    assert probe.session_count == 1
    assert probe.bytes > 0
    assert probe.journal_mode is not None
