"""Shared MCP list/manage helpers for `fastfold mcp` and interactive `/mcp`."""

from __future__ import annotations

from typing import Any

from rich.console import Console
from rich.table import Table

from agent.mcp_catalog import MCP_CATALOG, get_catalog_entry
from agent_server.mcp_service import McpService
from agent_server.store import AgentStore


def _store() -> AgentStore:
    return AgentStore()


def _service(store: AgentStore | None = None) -> McpService:
    return McpService(store or _store())


def resolve_server_ref(ref: str, store: AgentStore | None = None):
    """Resolve catalog id, server UUID, or case-insensitive name."""
    agent_store = store or _store()
    key = (ref or "").strip()
    if not key:
        return None, None
    # Catalog id first
    entry = get_catalog_entry(key.lower())
    if entry:
        server = next(
            (
                s
                for s in agent_store.list_mcp_servers()
                if getattr(s, "catalog_id", None) == entry.id
            ),
            None,
        )
        return entry, server
    servers = agent_store.list_mcp_servers()
    for server in servers:
        if server.id == key or server.id.startswith(key):
            return (
                get_catalog_entry(server.catalog_id) if server.catalog_id else None,
                server,
            )
    lowered = key.lower()
    for server in servers:
        if server.name.lower() == lowered:
            return (
                get_catalog_entry(server.catalog_id) if server.catalog_id else None,
                server,
            )
    return None, None


def print_mcp_status(console: Console) -> None:
    """Print suggested catalog + registered servers (Deep Agents–style /mcp view)."""
    service = _service()
    catalog = service.catalog_statuses()
    servers = service.store.list_mcp_servers()

    console.print("\n[bold]Suggested MCP servers[/bold] [dim](off until Connect)[/dim]")
    table = Table(show_header=True, header_style="bold")
    table.add_column("ID")
    table.add_column("Name")
    table.add_column("Auth")
    table.add_column("Status")
    table.add_column("Transport")
    for row in catalog:
        if row.get("connected"):
            status = "[green]connected[/green]"
        elif row.get("enabled"):
            status = "[yellow]enabled (auth?)[/yellow]"
        elif row.get("configured"):
            status = "[yellow]key saved[/yellow]"
        else:
            status = "[dim]off[/dim]"
        auth = row.get("auth_method") or row.get("preferred_auth") or row.get("auth_mode")
        table.add_row(
            str(row.get("id")),
            str(row.get("name")),
            str(auth),
            status,
            str(row.get("transport")),
        )
    console.print(table)

    custom = [s for s in servers if not getattr(s, "catalog_id", None)]
    console.print("\n[bold]Registered servers[/bold] [dim](agent-server DB)[/dim]")
    reg = Table(show_header=True, header_style="bold")
    reg.add_column("ID", max_width=12)
    reg.add_column("Name")
    reg.add_column("Catalog")
    reg.add_column("Enabled")
    reg.add_column("Transport")
    reg.add_column("Target", overflow="fold")
    if not servers:
        console.print("  [dim]No MCP servers registered yet.[/dim]")
    else:
        for server in servers:
            target = server.url or (
                f"{server.command} {' '.join(server.args)}".strip() if server.command else "—"
            )
            reg.add_row(
                server.id[:8],
                server.name,
                server.catalog_id or "—",
                "[green]on[/green]" if server.enabled else "[dim]off[/dim]",
                server.transport,
                target,
            )
        console.print(reg)
        if custom:
            console.print(
                f"  [dim]{len(custom)} custom server(s); "
                f"{len(servers) - len(custom)} from catalog[/dim]"
            )

    console.print(
        "\n  [dim]Commands:[/dim] list · catalog · connect <id> · disconnect <id> · "
        "enable/disable <id> · validate <id> · add · remove <id> · tools <id>"
    )
    console.print(
        "  [dim]Dashboard:[/dim] /dashboard/mcp · "
        "[dim]Runtime:[/dim] langchain MultiServerMCPClient (stdio/sse/http + headers)\n"
    )


def handle_mcp_argv(args: list[str], console: Console) -> int:
    """
    Execute mcp subcommand args (without leading 'mcp').

    Returns process-style exit code (0 ok, 1 error, 2 usage).
    """
    if not args or args[0] in {"list", "status", "ls"}:
        print_mcp_status(console)
        return 0

    action = args[0].lower()
    store = _store()
    service = _service(store)

    if action == "catalog":
        for row in service.catalog_statuses():
            console.print(
                f"  [cyan]{row['id']}[/cyan]  {row['name']}  "
                f"[dim]{row['auth_mode']}[/dim]  {row['url']}"
            )
        return 0

    if action == "connect":
        if len(args) < 2:
            console.print("  [red]Usage:[/red] mcp connect <catalog_id> [--api-key KEY]")
            return 2
        catalog_id = args[1].lower()
        entry = get_catalog_entry(catalog_id)
        if entry is None:
            console.print(f"  [red]Unknown catalog id:[/red] {catalog_id}")
            console.print(
                "  [dim]Available:[/dim] " + ", ".join(e.id for e in MCP_CATALOG)
            )
            return 1
        api_key: str | None = None
        if "--api-key" in args:
            idx = args.index("--api-key")
            if idx + 1 >= len(args):
                console.print("  [red]--api-key requires a value[/red]")
                return 2
            api_key = args[idx + 1]
        method = "api_key" if api_key or entry.auth_mode == "api_key" else "oauth"
        if method == "oauth" and entry.preferred_auth == "oauth" and not api_key:
            if entry.auth_mode == "oauth" or entry.auth_mode == "api_key_or_oauth":
                try:
                    result = service.start_oauth(catalog_id)
                except Exception as exc:  # noqa: BLE001
                    console.print(f"  [red]OAuth start failed:[/red] {exc}")
                    if entry.auth_mode != "oauth":
                        console.print(
                            "  [dim]Tip: mcp connect "
                            f"{catalog_id} --api-key <KEY>[/dim]"
                        )
                    return 1
                console.print(
                    f"  Open in browser:\n  [link]{result['authorizeUrl']}[/link]"
                )
                console.print(
                    "  After login, the agent server callback enables the MCP. "
                    "Or use Dashboard → MCP → Connect."
                )
                return 0
        if not api_key:
            console.print(
                f"  [red]API key required.[/red] mcp connect {catalog_id} --api-key <KEY>"
            )
            return 2
        try:
            result = service.connect_with_api_key(catalog_id, api_key)
        except Exception as exc:  # noqa: BLE001
            console.print(f"  [red]Connect failed:[/red] {exc}")
            return 1
        if result.get("ok"):
            console.print(
                f"  [green]Connected[/green] {entry.name} — "
                f"{result.get('toolCount', 0)} tools · enabled"
            )
            return 0
        console.print(f"  [red]Connect failed:[/red] {result.get('message')}")
        return 1

    if action == "disconnect":
        if len(args) < 2:
            console.print("  [red]Usage:[/red] mcp disconnect <catalog_id>")
            return 2
        catalog_id = args[1].lower()
        try:
            service.disconnect(catalog_id)
        except KeyError:
            console.print(f"  [red]Unknown catalog id:[/red] {catalog_id}")
            return 1
        console.print(f"  [green]Disconnected[/green] {catalog_id}")
        return 0

    if action in {"enable", "disable"}:
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

    if action in {"validate", "tools", "probe"}:
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

    if action == "add":
        # mcp add <name> --url URL [--transport http|sse]
        # mcp add <name> --command CMD [--arg x ...]
        if len(args) < 2:
            console.print(
                "  [red]Usage:[/red] mcp add <name> --url URL | --command CMD [--arg ...]"
            )
            return 2
        name = args[1]
        url: str | None = None
        command: str | None = None
        transport = "streamable_http"
        cmd_args: list[str] = []
        i = 2
        while i < len(args):
            tok = args[i]
            if tok == "--url" and i + 1 < len(args):
                url = args[i + 1]
                i += 2
                continue
            if tok == "--command" and i + 1 < len(args):
                command = args[i + 1]
                i += 2
                continue
            if tok in {"--arg", "--args"} and i + 1 < len(args):
                cmd_args.append(args[i + 1])
                i += 2
                continue
            if tok == "--transport" and i + 1 < len(args):
                raw = args[i + 1].lower().replace("-", "_")
                if raw in {"http", "streamable_http", "streamablehttp"}:
                    transport = "streamable_http"
                elif raw == "sse":
                    transport = "sse"
                elif raw == "stdio":
                    transport = "stdio"
                else:
                    console.print(f"  [red]Unknown transport:[/red] {args[i + 1]}")
                    return 2
                i += 2
                continue
            console.print(f"  [red]Unknown flag:[/red] {tok}")
            return 2
        if url:
            server = store.create_mcp_server(
                name=name,
                transport=transport if transport != "stdio" else "streamable_http",
                command=None,
                args=[],
                url=url,
                enabled=True,
            )
        elif command:
            server = store.create_mcp_server(
                name=name,
                transport="stdio",
                command=command,
                args=cmd_args,
                url=None,
                enabled=True,
            )
        else:
            console.print("  [red]Provide --url or --command[/red]")
            return 2
        console.print(
            f"  [green]Added[/green] {server.name} ({server.transport}) id={server.id[:8]}"
        )
        return 0

    if action in {"remove", "rm", "delete"}:
        if len(args) < 2:
            console.print("  [red]Usage:[/red] mcp remove <id|name>")
            return 2
        entry, server = resolve_server_ref(args[1], store)
        if server is None:
            console.print(f"  [red]Not found:[/red] {args[1]}")
            return 1
        if entry:
            # Catalog disconnect clears creds + disables; also delete row if requested
            try:
                service.disconnect(entry.id)
            except Exception:  # noqa: BLE001
                pass
        store.delete_mcp_server(server.id)
        console.print(f"  [green]Removed[/green] {server.name}")
        return 0

    if action in {"help", "-h", "--help"}:
        console.print(
            """
[bold]mcp[/bold] — list and manage MCP servers

  mcp / mcp list              Status (catalog + registered)
  mcp catalog                 Suggested cloud defaults
  mcp connect <id> [--api-key KEY]
  mcp disconnect <id>
  mcp enable|disable <id>
  mcp validate|tools <id>     Probe tools/list
  mcp add <name> --url URL
  mcp add <name> --command CMD [--arg ...]
  mcp remove <id|name>

Uses langchain-mcp-adapters MultiServerMCPClient (stdio / sse / streamable_http + headers).
Suggested servers: tamarind, latch, neurosnap, linear
"""
        )
        return 0

    console.print(f"  [red]Unknown mcp action:[/red] {action}")
    console.print("  [dim]Try:[/dim] mcp help")
    return 2
