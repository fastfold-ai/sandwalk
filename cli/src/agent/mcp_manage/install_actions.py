"""`mcp install` / `mcp doctor` for local featured servers (PyMOL, RayMol)."""

from __future__ import annotations

from rich.console import Console

from agent.mcp_catalog import get_catalog_entry
from agent.mcps.pymol_mcp import PLUGIN_ZIP_URL, pymol_doctor_checks
from agent.mcps.raymol_mcp import SETUP_URL as RAYMOL_SETUP_URL
from agent.mcps.raymol_mcp import raymol_doctor_checks
from agent_server.mcp_service import credentials_configured


def handle_install(args: list[str], console: Console, *, store, service) -> int:
    if len(args) < 2:
        console.print("  [red]Usage:[/red] mcp install <catalog-id> [--force]")
        console.print("  [dim]Examples:[/dim] mcp install pymol · mcp install raymol")
        console.print("  [dim]Reinstall:[/dim] mcp install pymol --force")
        return 2
    catalog_id = args[1].strip().lower()
    force = "--force" in args or "-f" in args
    entry = get_catalog_entry(catalog_id)
    if entry is None:
        console.print(f"  [red]Unknown catalog id:[/red] {catalog_id}")
        return 1

    if entry.transport == "stdio" or entry.auth_mode == "none":
        if catalog_id == "pymol":
            console.print(
                "  Reinstalling managed PyMOL MCP launcher…"
                if force
                else "  Installing managed PyMOL MCP launcher…"
            )
        elif catalog_id == "raymol":
            console.print(
                "  Checking RayMol app for MCP bridge…"
                if not force
                else "  Re-checking RayMol app for MCP bridge…"
            )
        try:
            result = service.install_featured(catalog_id, force=force)
        except RuntimeError as exc:
            console.print(f"  [red]{exc}[/red]")
            return 1
        except KeyError:
            console.print(f"  [red]Unknown catalog id:[/red] {catalog_id}")
            return 1
        if result.get("launcherMessage"):
            console.print(f"  [green]{result['launcherMessage']}[/green]")
        if catalog_id == "pymol":
            console.print(f"  [dim]Plugin zip:[/dim] {PLUGIN_ZIP_URL}")
            console.print(
                "  [dim]In PyMOL:[/dim] Plugin Manager → Install from URL → Start Listening"
            )
        elif catalog_id == "raymol":
            console.print(f"  [dim]Get RayMol:[/dim] {RAYMOL_SETUP_URL}")
            console.print(
                "  [dim]In RayMol:[/dim] toolbar RayMol MCP → Enable MCP server "
                "(use DMG/Homebrew build, not Mac App Store)"
            )
            console.print(
                "  [dim]When prompted:[/dim] click Allow for MCP access — "
                "otherwise the connection will not establish"
            )
        enable = result.get("enable") or {}
        if enable.get("ok"):
            console.print(
                f"  [green]Enabled[/green] {entry.name} "
                f"({enable.get('toolCount', '?')} tools)"
            )
            return 0
        if enable:
            console.print(
                f"  [yellow]Enabled with probe warning:[/yellow] "
                f"{enable.get('message')}"
            )
            if catalog_id == "raymol":
                console.print(
                    "  [dim]If tools fail: Enable MCP in the RayMol toolbar "
                    "and click Allow when prompted[/dim]"
                )
            else:
                console.print("  [dim]If tools fail: Start Listening in PyMOL[/dim]")
            return 0
        console.print(
            f"  [yellow]Registered {entry.name} but launcher is not ready.[/yellow]"
        )
        return 1

    try:
        result = service.install_featured(catalog_id)
    except KeyError:
        console.print(f"  [red]Unknown catalog id:[/red] {catalog_id}")
        return 1
    server = result["server"]
    console.print(
        f"  [green]Installed[/green] {server.name} (disabled). "
        f"Connect with: mcp connect {catalog_id}"
    )
    return 0


def _print_doctor_rows(console: Console, rows: list[dict[str, str]]) -> int:
    failed = 0
    for row in rows:
        status = row["status"]
        color = {"ok": "green", "warn": "yellow", "error": "red"}.get(status, "white")
        console.print(f"  [{color}]{status.upper()}[/{color}] {row['detail']}")
        if row.get("fix"):
            console.print(f"         [dim]fix:[/dim] {row['fix']}")
        if status == "error":
            failed += 1
    return failed


def handle_doctor(args: list[str], console: Console, *, store, service) -> int:
    catalog_id = args[1].strip().lower() if len(args) >= 2 else "pymol"
    entry = get_catalog_entry(catalog_id)
    if entry is None:
        console.print(f"  [red]Unknown catalog id:[/red] {catalog_id}")
        return 1

    console.print(f"  MCP doctor: {entry.name}")
    if catalog_id == "pymol":
        failed = _print_doctor_rows(console, pymol_doctor_checks())
        if not credentials_configured(entry):
            return 1
        result = service.validate(catalog_id=catalog_id)
        color = "green" if result.get("ok") else "yellow"
        console.print(f"  [{color}]probe[/{color}] {result.get('message')}")
        return 0 if failed == 0 else 1

    if catalog_id == "raymol":
        failed = _print_doctor_rows(console, raymol_doctor_checks())
        if not credentials_configured(entry):
            return 1
        result = service.validate(catalog_id=catalog_id)
        color = "green" if result.get("ok") else "yellow"
        console.print(f"  [{color}]probe[/{color}] {result.get('message')}")
        return 0 if failed == 0 else 1

    result = service.validate(catalog_id=catalog_id)
    color = "green" if result.get("ok") else "red"
    console.print(f"  [{color}]{result.get('message')}[/{color}]")
    return 0 if result.get("ok") else 1
