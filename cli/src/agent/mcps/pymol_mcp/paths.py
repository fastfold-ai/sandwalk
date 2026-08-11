"""Paths for the Sandwalk-managed PyMOL MCP launcher."""

from __future__ import annotations

from pathlib import Path

PLUGIN_VERSION = "0.0.1"
PLUGIN_ZIP_URL = "https://sandwalk.sh/pymol/plugin.zip"
TOKEN_PATH = Path.home() / ".config" / "pymol-mcp" / "token"

# Vendored installable package (no runtime git fetch).
_VENDOR_DIRNAME = "agentic-pymol"


def vendor_package_path() -> Path:
    """Local path to the vendored agentic-pymol package (pyproject + sources)."""
    return Path(__file__).resolve().parent / "vendor" / _VENDOR_DIRNAME


def _config_dir() -> Path:
    from agent.config import CONFIG_DIR

    return Path(CONFIG_DIR)


def pymol_mcp_home() -> Path:
    return _config_dir() / "pymol-mcp"


def launcher_path() -> Path:
    return pymol_mcp_home() / "bin" / "agentic-pymol"


def venv_path() -> Path:
    return pymol_mcp_home() / "venv"


# Back-compat module-level names (resolved at import; prefer functions in new code).
PYMOL_MCP_HOME = Path.home() / ".sandwalk" / "pymol-mcp"
PYMOL_MCP_VENV = PYMOL_MCP_HOME / "venv"
PYMOL_MCP_BIN = PYMOL_MCP_HOME / "bin"
PYMOL_MCP_LAUNCHER = PYMOL_MCP_BIN / "agentic-pymol"


def launcher_ready() -> bool:
    path = launcher_path()
    return path.is_file() or path.is_symlink()


def token_ready() -> bool:
    if not TOKEN_PATH.is_file():
        return False
    try:
        return bool(TOKEN_PATH.read_text(encoding="utf-8").strip())
    except OSError:
        return False
