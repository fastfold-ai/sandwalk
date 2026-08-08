"""Verify RayMol is installed for the Sandwalk MCP bridge."""

from __future__ import annotations

from pathlib import Path

from agent.mcps.raymol_mcp.paths import (
    DEFAULT_APP_BINARY,
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
        # launcher_path falls back to /Applications/... — accept it when present
        # even if broader discovery missed (TCC / quarantine edge cases).
        fallback = launcher_path()
        if fallback.is_file():
            binary = fallback
    if binary is not None:
        # Persist so packaged Sandwalk Server can reuse the path later even if
        # /Applications discovery is flaky under the app's environment.
        try:
            from agent.config import Config

            config = Config.load()
            current = str(config.get("mcp.raymol_binary") or "").strip()
            resolved = str(binary)
            if current != resolved:
                config.set("mcp.raymol_binary", resolved)
                config.save()
        except Exception:  # noqa: BLE001 — never block install on config write
            pass
        return True, f"RayMol bridge ready: {binary} --mcp-bridge"
    if handoff_ready():
        # MCP is already enabled in a running RayMol (mcp.json present).
        path = launcher_path()
        return (
            True,
            f"RayMol MCP handoff found; bridge command: {path} --mcp-bridge",
        )
    checked = [
        str(DEFAULT_APP_BINARY),
        str(
            Path.home()
            / "Applications"
            / "RayMol.app"
            / "Contents"
            / "MacOS"
            / "RayMol"
        ),
        "PATH (RayMol)",
        "mdfind io.raymol.RayMol",
        f"handoff {HANDOFF_PATH}",
    ]
    return (
        False,
        "RayMol app not found. Install from https://raymol.io/ "
        "(direct DMG or Homebrew — Mac App Store builds omit MCP), "
        "then re-run: sandwalk mcp install raymol. "
        f"Checked: {', '.join(checked)}. "
        "Or set mcp.raymol_binary to the RayMol executable path.",
    )


def raymol_doctor_checks() -> list[dict[str, str]]:
    """Return structured doctor rows for RayMol MCP."""
    rows: list[dict[str, str]] = []
    binary = find_raymol_binary()
    if binary is not None:
        rows.append(
            {
                "name": "raymol_app",
                "status": "ok",
                "detail": f"RayMol binary: {binary}",
            }
        )
    elif launcher_ready():
        rows.append(
            {
                "name": "raymol_app",
                "status": "ok",
                "detail": (
                    f"RayMol bridge ready via handoff; command: {launcher_path()}"
                ),
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
