"""`mcp enable|disable` and `mcp validate|tools|probe` action handlers."""

from __future__ import annotations

from rich.console import Console

from .resolve import resolve_server_ref


def handle_enable_disable(action: str, args: list[str], console: Console, *, store, service) -> int:
    if len(args) < 2:
        console.print(f"  [red]Usage:[/red] mcp {action} <id|name>")
        return 2
    entry, server = resolve_server_ref(args[1], store)
    if server is None and entry is not None:
        server = service.ensure_catalog_server(entry.id, enabled=False)
    if server is None:
        console.print(f"  [red]Not found:[/red] {args[1]}")
        return 1
    enabled = action == "enable"
    if enabled and entry:
        from agent_server.mcp_service import credentials_configured

        if not credentials_configured(entry):
            if entry.transport == "stdio" or entry.auth_mode == "none":
                console.print(
                    f"  [red]{entry.name} launcher is not installed.[/red] "
                    f"Run: mcp install {entry.id}"
                )
            else:
                console.print(
                    f"  [red]{entry.name} is not connected.[/red] "
                    f"Run: mcp connect {entry.id}"
                )
            return 1
    store.update_mcp_server(server.id, enabled=enabled)
    console.print(
        f"  [green]{'Enabled' if enabled else 'Disabled'}[/green] {server.name}"
    )
    return 0


def handle_validate(action: str, args: list[str], console: Console, *, store, service) -> int:
    if len(args) < 2:
        console.print(f"  [red]Usage:[/red] mcp {action} <id|name>")
        return 2
    entry, server = resolve_server_ref(args[1], store)
    try:
        if entry:
            result = service.validate(catalog_id=entry.id)
        elif server:
            result = service.validate(server_id=server.id)
        else:
            console.print(f"  [red]Not found:[/red] {args[1]}")
            return 1
    except Exception as exc:  # noqa: BLE001
        console.print(f"  [red]Validate failed:[/red] {exc}")
        return 1
    ok = bool(result.get("ok"))
    color = "green" if ok else "red"
    console.print(f"  [{color}]{result.get('message')}[/{color}]")
    tools = result.get("tools") or []
    if tools:
        console.print(f"  [dim]Tools ({result.get('toolCount', len(tools))}):[/dim]")
        for name in tools[:40]:
            console.print(f"    · {name}")
        if len(tools) > 40:
            console.print(f"    [dim]… +{len(tools) - 40} more[/dim]")
    return 0 if ok else 1
