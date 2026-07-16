"""Setup wizard step: connect suggested MCP servers."""

import sys

import typer

from cli.app import console
from cli.setup.keys import _prompt_masked_secret


def _prompt_setup_mcps(mcp_arg: str | None = None, skip: bool = False) -> None:
    """Setup step: connect suggested MCP servers (optional)."""
    from agent.mcp_catalog import MCP_CATALOG, get_catalog_entry
    from agent.mcp_manage import handle_mcp_argv

    if skip:
        return

    ids: list[str] = []
    if mcp_arg:
        ids = [s.strip().lower() for s in mcp_arg.split(",") if s.strip()]
    else:
        interactive = sys.stdin.isatty() and sys.stdout.isatty()
        if not interactive:
            console.print(
                "\n  [dim]Skipping MCP setup (non-interactive). "
                "Connect later with `sandwalk mcp connect <id>`.[/dim]"
            )
            return
        console.print("\n  [cyan]MCP servers[/cyan]")
        console.print(
            "  [dim]Connect remote tool servers (optional). "
            "Catalog ids:[/dim] " + ", ".join(e.id for e in MCP_CATALOG)
        )
        try:
            proceed = input("  Connect MCP servers now? [y/N] ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            console.print("\n  [dim]Setup cancelled.[/dim]")
            raise typer.Exit()
        if proceed not in ("y", "yes"):
            console.print(
                "  [dim]Skipped. Connect later with `sandwalk mcp connect <id>` "
                "or Dashboard → MCP.[/dim]"
            )
            return
        try:
            raw = input(
                "  Catalog ids to connect (comma-separated; Enter to skip): "
            ).strip()
        except (EOFError, KeyboardInterrupt):
            raw = ""
        ids = [s.strip().lower() for s in raw.split(",") if s.strip()]

    if not ids:
        console.print("  [dim]No MCP servers selected.[/dim]")
        return

    for catalog_id in ids:
        entry = get_catalog_entry(catalog_id)
        if entry is None:
            console.print(f"  [yellow]Unknown MCP catalog id:[/yellow] {catalog_id}")
            continue
        argv = ["connect", catalog_id]
        if entry.auth_mode in {"api_key", "api_key_or_oauth"} and entry.preferred_auth != "oauth":
            try:
                key = _prompt_masked_secret(
                    f"  API key for {entry.name} (Enter to skip): "
                ).strip()
            except (EOFError, KeyboardInterrupt):
                key = ""
            if not key:
                console.print(f"  [dim]Skipped {entry.name}.[/dim]")
                continue
            argv.extend(["--api-key", key])
        code = handle_mcp_argv(argv, console)
        if code != 0:
            console.print(
                f"  [yellow]Could not finish connect for {catalog_id}.[/yellow] "
                "Use Dashboard → MCP or `sandwalk mcp connect`."
            )
