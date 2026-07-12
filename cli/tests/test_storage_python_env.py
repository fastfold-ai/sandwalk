"""Tests for Python environment sizing in Storage."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from agent_server.storage_service import (
    list_installed_packages,
    resolve_python_env_root,
    StorageService,
)


def test_resolve_python_env_root_from_venv(tmp_path: Path):
    root = tmp_path / "venv"
    bin_dir = root / "bin"
    bin_dir.mkdir(parents=True)
    (root / "pyvenv.cfg").write_text("home = /usr\n", encoding="utf-8")
    python = bin_dir / "python"
    python.write_text("#!/bin/sh\n", encoding="utf-8")

    assert resolve_python_env_root(python) == root.resolve()


def test_resolve_python_env_root_conda(tmp_path: Path):
    root = tmp_path / "claude-science-mcp"
    bin_dir = root / "bin"
    bin_dir.mkdir(parents=True)
    (root / "conda-meta").mkdir()
    python = bin_dir / "python"
    python.write_text("#!/bin/sh\n", encoding="utf-8")

    assert resolve_python_env_root(python) == root.resolve()


def test_list_installed_packages_includes_known_dist():
    packages = list_installed_packages()
    assert packages
    names = {name.lower() for name, _version in packages}
    # pytest is always present when running this suite.
    assert "pytest" in names


def test_storage_report_includes_python_env(tmp_path: Path):
    home = tmp_path / "fastfold-home"
    home.mkdir()
    env_root = tmp_path / "agent-venv"
    (env_root / "bin").mkdir(parents=True)
    (env_root / "pyvenv.cfg").write_text("home = /usr\n", encoding="utf-8")
    (env_root / "lib").mkdir()
    (env_root / "lib" / "marker.txt").write_text("x" * 2048, encoding="utf-8")

    with (
        patch(
            "agent_server.storage_service.resolve_python_env_root",
            return_value=env_root,
        ),
        patch(
            "agent_server.storage_service.list_installed_packages",
            return_value=[("numpy", "2.0.0"), ("pandas", "2.2.0")],
        ),
    ):
        report = StorageService().get_report(home=home)

    python = next(item for item in report.categories if item.id == "python_env")
    assert python.bytes >= 2048
    assert python.path == str(env_root)
    assert [child.label for child in python.children] == [
        "numpy 2.0.0",
        "pandas 2.2.0",
    ]
    assert report.total_bytes >= python.bytes
    # Home location total excludes the external python env.
    assert report.location.bytes == report.total_bytes - python.bytes
