"""`mcp` / `mcp list` status view: suggested catalog + registered servers."""

from __future__ import annotations

from rich.console import Console
from rich.table import Table

from .resolve import _service


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
