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
    on_removable_volume,
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
        message = f"RayMol bridge ready: {binary} --mcp-bridge"
        if on_removable_volume(binary):
            message += (
                " (running from a mounted volume — drag RayMol.app to "
                "/Applications so the bridge keeps working after eject)"
            )
        return True, message
    if handoff_ready():
        # MCP handoff exists but no binary: RayMol wrote mcp.json and then went
        # away (quit and deleted, or DMG ejected). Reporting ready here would only
        # defer the failure to an ENOENT when the bridge is spawned.
        _clear_stale_binary_config()
        return (
            False,
            "RayMol MCP handoff found but the RayMol app is missing. Reopen RayMol "
            "(install from https://raymol.io/ if needed) and re-run: "
            "sandwalk mcp install raymol. If you launched RayMol from its DMG, "
            "drag RayMol.app to /Applications first.",
        )
    _clear_stale_binary_config()
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
        "running RayMol process",
        "mdfind io.raymol.RayMol",
        "/Volumes/*/RayMol.app",
        "Homebrew Caskroom",
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


def _clear_stale_binary_config() -> None:
    """Drop ``mcp.raymol_binary`` when it points at a path that no longer exists."""
    try:
        from agent.config import Config

        config = Config.load()
        raw = str(config.get("mcp.raymol_binary") or "").strip()
        if raw and not Path(raw).expanduser().is_file():
            config.set("mcp.raymol_binary", "")
            config.save()
    except Exception:  # noqa: BLE001 — best-effort cleanup
        pass


def raymol_doctor_checks() -> list[dict[str, str]]:
    """Return structured doctor rows for RayMol MCP."""
    rows: list[dict[str, str]] = []
    binary = find_raymol_binary()
    if binary is not None:
        detail = f"RayMol binary: {binary}"
        if on_removable_volume(binary):
            detail += " (mounted volume — copy to /Applications to survive eject)"
        rows.append(
            {
                "name": "raymol_app",
                "status": "warn" if on_removable_volume(binary) else "ok",
                "detail": detail,
            }
        )
    elif handoff_ready():
        rows.append(
            {
                "name": "raymol_app",
                "status": "error",
                "detail": (
                    "MCP handoff present but the RayMol app is missing — the bridge "
                    "cannot be spawned"
                ),
                "fix": (
                    "Reopen RayMol (drag it to /Applications if you ran it from the "
                    f"DMG), or install from {SETUP_URL}"
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
