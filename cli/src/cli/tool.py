"""`sandwalk tool` — run individual tools directly."""

import typer

from cli.app import app, console

tool_app = typer.Typer(help="Run individual tools directly")
app.add_typer(tool_app, name="tool")


@tool_app.command("list")
def tool_list():
    """List all available tools."""
    from tools import ensure_loaded, registry, tool_load_errors

    ensure_loaded()
    console.print(registry.list_tools_table())
    errors = tool_load_errors()
    if errors:
        names = ", ".join(sorted(errors.keys())[:8])
        extra = "" if len(errors) <= 8 else f" (+{len(errors) - 8} more)"
        console.print(
            f"[yellow]Warning:[/yellow] {len(errors)} tool module(s) failed to load: {names}{extra}"
        )
