"""Verify RayMol is installed for the Sandwalk MCP bridge."""

from __future__ import annotations

from agent.mcps.raymol_mcp.paths import (
    HANDOFF_PATH,
    SETUP_URL,
    find_raymol_binary,
    handoff_ready,
    launcher_path,
    launcher_ready,
)


def ensure_launcher(*, force: bool = False) -> tuple[bool, str]:
    """Confirm the RayMol binary exists (no managed venv — RayMol owns MCP).

    ``force`` re-resolves the path; there is nothing to reinstall.
    """
    _ = force
    binary = find_raymol_binary()
    if binary is None:
        return (
            False,
            "RayMol app not found. Install from https://raymol.io/ "
            "(direct DMG or Homebrew — Mac App Store builds omit MCP), "
            "then re-run: sandwalk mcp install raymol",
        )
    return True, f"RayMol bridge ready: {binary} --mcp-bridge"


def raymol_doctor_checks() -> list[dict[str, str]]:
    """Return structured doctor rows for RayMol MCP."""
    rows: list[dict[str, str]] = []
    binary = find_raymol_binary()
    if launcher_ready() and binary is not None:
        rows.append(
            {
                "name": "raymol_app",
                "status": "ok",
                "detail": f"RayMol binary: {binary}",
            }
        )
    else:
        rows.append(
            {
                "name": "raymol_app",
                "status": "error",
                "detail": f"Missing RayMol at {launcher_path()}",
                "fix": f"Install from {SETUP_URL} (DMG or Homebrew, not Mac App Store)",
            }
        )
    if handoff_ready():
        rows.append(
            {
                "name": "raymol_mcp_enabled",
                "status": "ok",
                "detail": f"MCP handoff: {HANDOFF_PATH}",
            }
        )
    else:
        rows.append(
            {
                "name": "raymol_mcp_enabled",
                "status": "warn",
                "detail": f"No MCP handoff at {HANDOFF_PATH}",
                "fix": (
                    "Open RayMol → toolbar RayMol MCP → Enable MCP server, "
                    "then click Allow when RayMol prompts for MCP access"
                ),
            }
        )
    return rows
