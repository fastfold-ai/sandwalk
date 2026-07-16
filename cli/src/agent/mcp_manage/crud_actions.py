"""`mcp add` and `mcp remove` action handlers."""

from __future__ import annotations

from rich.console import Console

from .resolve import resolve_server_ref


def handle_add(args: list[str], console: Console, *, store) -> int:
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


def handle_remove(args: list[str], console: Console, *, store, service) -> int:
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
