"""Pytest fixtures for HOME-isolated sandwalk functional tests."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def cli_home(tmp_path: Path) -> Path:
    """Empty home directory — Config uses ``Path.home() / '.sandwalk'``."""
    home = tmp_path / "home"
    home.mkdir()
    return home


@pytest.fixture
def cli_cwd(tmp_path: Path) -> Path:
    cwd = tmp_path / "cwd"
    cwd.mkdir()
    return cwd
