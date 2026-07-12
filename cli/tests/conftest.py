"""Shared pytest configuration and fixtures."""

import os
import sys
from pathlib import Path
import pytest

# Ensure `src/` packages import when running from repo root without editable install.
SRC_PATH = Path(__file__).resolve().parents[1] / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))


def pytest_addoption(parser):
    parser.addoption(
        "--run-e2e", action="store_true", default=False,
        help="Run end-to-end tests that hit real APIs",
    )


def pytest_collection_modifyitems(config, items):
    if config.getoption("--run-e2e"):
        return  # Run all tests including e2e
    # Skip e2e tests by default
    skip_e2e = pytest.mark.skip(reason="Need --run-e2e to run")
    for item in items:
        if "test_e2e" in item.nodeid or "e2e" in item.keywords:
            item.add_marker(skip_e2e)


@pytest.fixture(autouse=True)
def _isolate_cli_config(tmp_path, monkeypatch):
    """Redirect the CLI config dir to a temp path for every test.

    Tests construct ``Config`` instances and exercise CLI flows that call
    ``Config.save()``, which writes to the real ``~/.fastfold-cli/config.json``.
    Without this guard, running the suite outside a filesystem sandbox clobbers
    the user's actual API keys. Pointing the module-level path constants at a
    per-test temp dir makes config writes hermetic.
    """
    import agent.config as _cfg

    cfg_dir = tmp_path / "fastfold-cli-config"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(_cfg, "CONFIG_DIR", cfg_dir, raising=False)
    monkeypatch.setattr(_cfg, "CONFIG_FILE", cfg_dir / "config.json", raising=False)
    monkeypatch.setattr(_cfg, "CONFIG_BACKUP_FILE", cfg_dir / "config.json.bak", raising=False)
    yield


def has_api_key():
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def _has_cellxgene():
    try:
        import cellxgene_census
        return True
    except ImportError:
        return False


# ---------------------------------------------------------------------------
# Rich console capture fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def captured_console():
    """Yield a (console, buffer) tuple for capturing Rich output."""
    from io import StringIO
    from rich.console import Console
    buf = StringIO()
    console = Console(file=buf, force_terminal=True, width=120)
    return console, buf
