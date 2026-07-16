"""`sandwalk mcp` — list and manage MCP servers (catalog defaults + custom)."""

import typer

from cli.app import app, console

mcp_app = typer.Typer(
    help="List and manage MCP servers (catalog defaults + custom)",
    invoke_without_command=True,
)
app.add_typer(mcp_app, name="mcp")


@mcp_app.callback(invoke_without_command=True)
def mcp_root(ctx: typer.Context):
    """Show MCP status (same as `sandwalk mcp list`)."""
    if ctx.invoked_subcommand is not None:
        return
    from agent.mcp_manage import handle_mcp_argv

    code = handle_mcp_argv(["list"], console)
    if code:
        raise typer.Exit(code=code)


@mcp_app.command("list")
def mcp_list_cmd():
    """List suggested catalog + registered MCP servers."""
    from agent.mcp_manage import handle_mcp_argv

    code = handle_mcp_argv(["list"], console)
    if code:
        raise typer.Exit(code=code)


@mcp_app.command("catalog")
def mcp_catalog_cmd():
    """Show suggested cloud MCP defaults."""
    from agent.mcp_manage import handle_mcp_argv

    code = handle_mcp_argv(["catalog"], console)
    if code:
        raise typer.Exit(code=code)


@mcp_app.command("connect")
def mcp_connect_cmd(
    catalog_id: str = typer.Argument(
        ..., help="Catalog id (tamarind|latch|neurosnap|paperclip|linear)"
    ),
    api_key: str | None = typer.Option(
        None,
        "--api-key",
        help="API key (required for neurosnap/tamarind; optional for paperclip/linear)",
        hide_input=True,
    ),
):
    """Connect a suggested MCP (API key or OAuth browser URL)."""
    from agent.mcp_manage import handle_mcp_argv

    argv = ["connect", catalog_id]
    if api_key:
        argv.extend(["--api-key", api_key])
    code = handle_mcp_argv(argv, console)
    if code:
        raise typer.Exit(code=code)


@mcp_app.command("disconnect")
def mcp_disconnect_cmd(
    catalog_id: str = typer.Argument(..., help="Catalog id to disconnect"),
):
    """Clear credentials and disable a catalog MCP."""
    from agent.mcp_manage import handle_mcp_argv

    code = handle_mcp_argv(["disconnect", catalog_id], console)
    if code:
        raise typer.Exit(code=code)


@mcp_app.command("enable")
def mcp_enable_cmd(ref: str = typer.Argument(..., help="Catalog id, server id, or name")):
    """Enable a registered MCP server."""
    from agent.mcp_manage import handle_mcp_argv

    code = handle_mcp_argv(["enable", ref], console)
    if code:
        raise typer.Exit(code=code)


@mcp_app.command("disable")
def mcp_disable_cmd(ref: str = typer.Argument(..., help="Catalog id, server id, or name")):
    """Disable a registered MCP server."""
    from agent.mcp_manage import handle_mcp_argv

    code = handle_mcp_argv(["disable", ref], console)
    if code:
        raise typer.Exit(code=code)


@mcp_app.command("validate")
def mcp_validate_cmd(ref: str = typer.Argument(..., help="Catalog id, server id, or name")):
    """Probe MCP initialize + tools/list."""
    from agent.mcp_manage import handle_mcp_argv

    code = handle_mcp_argv(["validate", ref], console)
    if code:
        raise typer.Exit(code=code)


@mcp_app.command("tools")
def mcp_tools_cmd(ref: str = typer.Argument(..., help="Catalog id, server id, or name")):
    """List tools from an MCP server (same as validate)."""
    from agent.mcp_manage import handle_mcp_argv

    code = handle_mcp_argv(["tools", ref], console)
    if code:
        raise typer.Exit(code=code)


@mcp_app.command("add")
def mcp_add_cmd(
    name: str = typer.Argument(..., help="Server display name"),
    url: str | None = typer.Option(None, "--url", help="Remote MCP URL"),
    command: str | None = typer.Option(None, "--command", help="stdio command"),
    arg: list[str] = typer.Option(None, "--arg", help="stdio arg (repeatable)"),
    transport: str = typer.Option(
        "http",
        "--transport",
        help="http|sse|stdio (http = streamable_http)",
    ),
):
    """Add a custom MCP server."""
    from agent.mcp_manage import handle_mcp_argv

    argv = ["add", name, "--transport", transport]
    if url:
        argv.extend(["--url", url])
    if command:
        argv.extend(["--command", command])
    for value in arg or []:
        argv.extend(["--arg", value])
    code = handle_mcp_argv(argv, console)
    if code:
        raise typer.Exit(code=code)


@mcp_app.command("remove")
def mcp_remove_cmd(ref: str = typer.Argument(..., help="Catalog id, server id, or name")):
    """Remove a registered MCP server."""
    from agent.mcp_manage import handle_mcp_argv

    code = handle_mcp_argv(["remove", ref], console)
    if code:
        raise typer.Exit(code=code)
