"""`mcp catalog` / `mcp connect` / `mcp disconnect` action handlers."""

from __future__ import annotations

from rich.console import Console

from agent.mcp_catalog import MCP_CATALOG, get_catalog_entry


def handle_catalog(args: list[str], console: Console, *, service) -> int:
    for row in service.catalog_statuses():
        console.print(
            f"  [cyan]{row['id']}[/cyan]  {row['name']}  "
            f"[dim]{row['auth_mode']}[/dim]  {row['url']}"
        )
    return 0


def handle_connect(args: list[str], console: Console, *, service) -> int:
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
            f"{result.get('toolCount', 0)} tools · configured"
            + (
                " · enabled"
                if result.get("enabled")
                else " · disabled (mcp enable to turn on)"
            )
        )
        return 0
    console.print(f"  [red]Connect failed:[/red] {result.get('message')}")
    return 1


def handle_disconnect(args: list[str], console: Console, *, service) -> int:
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
