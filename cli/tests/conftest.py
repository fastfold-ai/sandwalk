"""Shared pytest configuration and fixtures."""

import os
import sys
import tempfile
from pathlib import Path

import pytest

# Ensure `src/` packages import when running from repo root without editable install.
SRC_PATH = Path(__file__).resolve().parents[1] / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

# Keep the suite off the developer's own ~/.sandwalk. A dozen call sites build
# ``AgentStore()`` with no path, which resolves through ``Path.home()`` to the
# database the user is actually working in — running the suite used to rewrite
# it, and a half-written store then looked corrupt on the next start. The
# per-test CONFIG_DIR fixture below cannot cover this on its own: constants are
# bound at import time and subprocesses inherit the environment, not monkey
# patches. This must run before anything imports ``agent.config``.
_FAKE_HOME = Path(tempfile.mkdtemp(prefix="sandwalk-test-home-"))
os.environ["HOME"] = str(_FAKE_HOME)
os.environ["USERPROFILE"] = str(_FAKE_HOME)

# ``agent.config`` calls ``load_dotenv()`` at import, which searches upward from
# the working directory. A developer with a ``~/.env`` (or one above the repo)
# therefore leaks real provider keys into the suite: setup-wizard tests then see
# an "existing key", take the interactive branch, and block on ``input()``.
#
# Deleting the vars here is not enough — that import happens later, during
# collection, and would re-inject them. python-dotenv defaults to
# ``override=False``, so pinning each var to empty makes it skip them, and the
# config layer normalizes blank secrets to None. Opt-in lanes that need live
# credentials set their own env gates, so leave the real values alone there.
_PROVIDER_KEY_ENV_VARS = (
    "FASTFOLD_API_KEY",
    "BOLTZ_API_KEY",
    "ANTHROPIC_API_KEY",
    "OPENAI_API_KEY",
    "XAI_API_KEY",
    "GEMINI_API_KEY",
    "MOONSHOT_API_KEY",
    "NVIDIA_API_KEY",
    "OPENCODE_API_KEY",
    "DEEPSEEK_API_KEY",
    "MINIMAX_API_KEY",
    "MISTRAL_API_KEY",
    "QWEN_API_KEY",
    "TOGETHER_API_KEY",
    "OPENROUTER_API_KEY",
)
if not any(
    os.environ.get(gate, "").strip().lower() in {"1", "true", "yes"}
    for gate in ("RUN_CLI_NETWORK", "RUN_CLI_E2E", "RUN_MODAL_E2E")
):
    for _var in _PROVIDER_KEY_ENV_VARS:
        os.environ[_var] = ""


def _env_flag(name: str) -> bool:
    return os.environ.get(name, "").strip().lower() in {"1", "true", "yes"}


def pytest_addoption(parser):
    parser.addoption(
        "--run-e2e",
        action="store_true",
        default=False,
        help="Run end-to-end tests that hit real APIs (same as RUN_CLI_E2E=1)",
    )


# Opt-in lanes — excluded from plain `pytest tests/` / CI unless their gate is on.
# Keeps CI/scripts free of the long `-m "not X and not Y…"` expression.
_OPT_IN_MARKERS: tuple[tuple[str, str], ...] = (
    ("data_smoke", "RUN_DATA_SMOKE"),
    ("integration", "RUN_INTEGRATION"),
    ("modal_e2e", "RUN_MODAL_E2E"),
    ("cli_network", "RUN_CLI_NETWORK"),
    ("cli_e2e", "RUN_CLI_E2E"),
    ("e2e", "RUN_CLI_E2E"),
)


def pytest_collection_modifyitems(config, items):
    run_e2e = bool(config.getoption("--run-e2e")) or _env_flag("RUN_CLI_E2E")

    def _enabled(marker: str, env_name: str) -> bool:
        if marker in {"e2e", "cli_e2e"}:
            return run_e2e
        return _env_flag(env_name)

    selected: list = []
    deselected: list = []
    for item in items:
        blocked = False
        for marker, env_name in _OPT_IN_MARKERS:
            if marker in item.keywords and not _enabled(marker, env_name):
                blocked = True
                break
        if not blocked and "test_e2e" in item.nodeid and not run_e2e:
            blocked = True
        (deselected if blocked else selected).append(item)

    if deselected:
        config.hook.pytest_deselected(items=deselected)
    items[:] = selected


@pytest.fixture(autouse=True)
def _isolate_cli_config(tmp_path, monkeypatch):
    """Redirect the CLI config dir to a temp path for every test.

    Tests construct ``Config`` instances and exercise CLI flows that call
    ``Config.save()``, which writes to the real ``~/.sandwalk/config.json``.
    Without this guard, running the suite outside a filesystem sandbox clobbers
    the user's actual API keys. Pointing the module-level path constants at a
    per-test temp dir makes config writes hermetic.
    """
    import agent.config as _cfg

    cfg_dir = tmp_path / "sandwalk-config"
    cfg_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(_cfg, "CONFIG_DIR", cfg_dir, raising=False)
    monkeypatch.setattr(_cfg, "CONFIG_FILE", cfg_dir / "config.json", raising=False)
    monkeypatch.setattr(_cfg, "CONFIG_BACKUP_FILE", cfg_dir / "config.json.bak", raising=False)
    # Isolate agent-server auth settings so a developer machine with
    # auth_enabled=true does not 401 TestClient suites.
    settings_path = tmp_path / "sandwalk-auth-settings.json"
    monkeypatch.setenv("SANDWALK_SETTINGS_PATH", str(settings_path))
    # Keep Modal token probes hermetic even when the host shell has tokens.
    monkeypatch.delenv("MODAL_TOKEN_ID", raising=False)
    monkeypatch.delenv("MODAL_TOKEN_SECRET", raising=False)
    # Re-pin provider keys every test so pytest-xdist workers cannot leak a
    # sibling test's setenv/os.environ mutation into validate/probe paths.
    if not any(
        _env_flag(gate) for gate in ("RUN_CLI_NETWORK", "RUN_CLI_E2E", "RUN_MODAL_E2E")
    ):
        for var in _PROVIDER_KEY_ENV_VARS:
            monkeypatch.setenv(var, "")
    yield


def has_api_key():
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def _has_cellxgene():
    try:
        import cellxgene_census  # noqa: F401
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
