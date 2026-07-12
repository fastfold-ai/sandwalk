"""Tests for Environment package catalog and service."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

import pytest

from agent_server.environment_catalog import (
    is_core_package,
    is_manageable_package,
    manageable_package_names,
)
from agent_server.environment_service import EnvironmentError, EnvironmentService


def test_catalog_marks_core_and_manageable():
    assert is_core_package("fastapi")
    assert is_core_package("LangChain")
    assert not is_manageable_package("fastapi")
    assert is_manageable_package("torch")
    assert is_manageable_package("rdkit")
    assert "scikit-learn" in manageable_package_names()


def test_get_report_includes_groups(tmp_path):
    with (
        patch(
            "agent_server.environment_service.resolve_python_env_root",
            return_value=tmp_path,
        ),
        patch(
            "agent_server.environment_service.list_installed_packages",
            return_value=[
                ("fastapi", "0.100.0"),
                ("rdkit", "2024.1"),
                ("numpy", "2.0.0"),
            ],
        ),
        patch("agent_server.environment_service._path_size_bytes", return_value=1234),
    ):
        report = EnvironmentService().get_report()

    assert report.env_bytes == 1234
    chemistry = next(g for g in report.groups if g.id == "chemistry")
    rdkit = next(p for p in chemistry.packages if p.name == "rdkit")
    assert rdkit.installed is True
    assert rdkit.version == "2024.1"
    assert rdkit.removable is True
    ml = next(g for g in report.groups if g.id == "ml")
    torch = next(p for p in ml.packages if p.name == "torch")
    assert torch.installed is False
    core_names = {p.name for p in report.core}
    assert "fastapi" in core_names
    assert "numpy" in core_names


def test_uninstall_rejects_core_package():
    with pytest.raises(EnvironmentError, match="core FastFold"):
        EnvironmentService().uninstall("fastapi")


def test_install_rejects_unknown_package():
    with pytest.raises(EnvironmentError, match="not in the skill/tool catalog"):
        EnvironmentService().install("totally-unknown-pkg-xyz")


def test_install_allows_unlisted_when_confirmed():
    completed = SimpleNamespace(returncode=0, stdout="ok", stderr="")
    with (
        patch("agent_server.environment_service._find_uv", return_value="/usr/bin/uv"),
        patch(
            "agent_server.environment_service.subprocess.run",
            return_value=completed,
        ),
        patch(
            "agent_server.environment_service.list_installed_packages",
            return_value=[("gseapy", "1.0.0")],
        ),
    ):
        # gseapy is in extended catalog — use a truly unlisted name
        result = EnvironmentService().install(
            "some-custom-wheel",
            allow_unlisted=True,
        )
    assert result.ok is True
    assert result.name == "some-custom-wheel"


def test_install_runs_uv_pip(tmp_path):
    completed = SimpleNamespace(returncode=0, stdout="ok", stderr="")
    with (
        patch("agent_server.environment_service._find_uv", return_value="/usr/bin/uv"),
        patch(
            "agent_server.environment_service.subprocess.run",
            return_value=completed,
        ) as run,
        patch(
            "agent_server.environment_service.list_installed_packages",
            return_value=[("rdkit", "2024.1")],
        ),
    ):
        result = EnvironmentService().install("rdkit")

    assert result.ok is True
    assert result.installed is True
    assert result.version == "2024.1"
    cmd = run.call_args.args[0]
    assert cmd[:3] == ["/usr/bin/uv", "pip", "install"]
    assert "rdkit" in cmd


def test_uninstall_runs_uv_pip():
    completed = SimpleNamespace(returncode=0, stdout="ok", stderr="")
    with (
        patch("agent_server.environment_service._find_uv", return_value="/usr/bin/uv"),
        patch(
            "agent_server.environment_service.subprocess.run",
            return_value=completed,
        ) as run,
        patch(
            "agent_server.environment_service.list_installed_packages",
            return_value=[],
        ),
    ):
        result = EnvironmentService().uninstall("torch")

    assert result.ok is True
    assert result.installed is False
    cmd = run.call_args.args[0]
    assert cmd[:4] == ["/usr/bin/uv", "pip", "uninstall", "-y"]
    assert "torch" in cmd
