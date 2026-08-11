"""`sandwalk specialists` — manage agent run profiles (skills + MCPs + instructions)."""

import typer

from cli.app import app, console

specialists_app = typer.Typer(
    help="Manage agent run profiles (skills + MCPs + instructions)",
    invoke_without_command=True,
)
app.add_typer(specialists_app, name="specialists")


@specialists_app.callback(invoke_without_command=True)
def specialists_root(ctx: typer.Context):
    """List specialists (same as `sandwalk specialists list`)."""
    if ctx.invoked_subcommand is not None:
        return
    from agent.specialists_manage import cmd_list

    code = cmd_list(console)
    if code:
        raise typer.Exit(code=code)


@specialists_app.command("list")
def specialists_list_cmd():
    """List specialists shared with the dashboard."""
    from agent.specialists_manage import cmd_list

    code = cmd_list(console)
    if code:
        raise typer.Exit(code=code)


@specialists_app.command("show")
def specialists_show_cmd(
    ref: str = typer.Argument(..., help="Slug, name, or id"),
):
    """Show one specialist."""
    from agent.specialists_manage import cmd_show

    code = cmd_show(console, ref)
    if code:
        raise typer.Exit(code=code)


@specialists_app.command("create")
def specialists_create_cmd(
    name: str = typer.Argument(..., help="Display name"),
    slug: str | None = typer.Option(None, "--slug", help="URL-safe slug"),
    description: str | None = typer.Option(None, "--description", "-d"),
    instructions: str | None = typer.Option(
        None, "--instructions", "-i", help="Extra system-prompt text"
    ),
    color: str = typer.Option("ink", "--color"),
    icon: str = typer.Option("agent", "--icon"),
    skill: list[str] | None = typer.Option(
        None, "--skill", "-s", help="Skill name (repeatable)"
    ),
    mcp: list[str] | None = typer.Option(
        None, "--mcp", help="MCP server id (repeatable)"
    ),
    use: bool = typer.Option(False, "--use", help="Activate for CLI runs"),
):
    """Create a specialist (same store as Dashboard → Specialists)."""
    from agent.specialists_manage import cmd_create

    code = cmd_create(
        console,
        name=name,
        slug=slug,
        description=description,
        instructions=instructions,
        color=color,
        icon=icon,
        skills=list(skill or []),
        mcps=list(mcp or []),
        use=use,
    )
    if code:
        raise typer.Exit(code=code)


@specialists_app.command("update")
def specialists_update_cmd(
    ref: str = typer.Argument(..., help="Slug, name, or id"),
    name: str | None = typer.Option(None, "--name"),
    slug: str | None = typer.Option(None, "--slug"),
    description: str | None = typer.Option(None, "--description", "-d"),
    clear_description: bool = typer.Option(False, "--clear-description"),
    instructions: str | None = typer.Option(None, "--instructions", "-i"),
    clear_instructions: bool = typer.Option(False, "--clear-instructions"),
    color: str | None = typer.Option(None, "--color"),
    icon: str | None = typer.Option(None, "--icon"),
    skill: list[str] | None = typer.Option(
        None, "--skill", "-s", help="Replace skill list (repeatable)"
    ),
    mcp: list[str] | None = typer.Option(
        None, "--mcp", help="Replace MCP id list (repeatable)"
    ),
):
    """Update a specialist."""
    from agent.specialists_manage import cmd_update

    code = cmd_update(
        console,
        ref,
        name=name,
        slug=slug,
        description=description,
        clear_description=clear_description,
        instructions=instructions,
        clear_instructions=clear_instructions,
        color=color,
        icon=icon,
        skills=None if skill is None else list(skill),
        mcps=None if mcp is None else list(mcp),
    )
    if code:
        raise typer.Exit(code=code)


@specialists_app.command("delete")
def specialists_delete_cmd(
    ref: str = typer.Argument(..., help="Slug, name, or id"),
):
    """Delete a specialist."""
    from agent.specialists_manage import cmd_delete

    code = cmd_delete(console, ref)
    if code:
        raise typer.Exit(code=code)


@specialists_app.command("use")
def specialists_use_cmd(
    ref: str = typer.Argument(..., help="Slug, name, or id"),
):
    """Activate a specialist for CLI interactive/batch runs."""
    from agent.specialists_manage import cmd_use

    code = cmd_use(console, ref)
    if code:
        raise typer.Exit(code=code)


@specialists_app.command("clear")
def specialists_clear_cmd():
    """Clear the active CLI specialist (use global skills/MCPs)."""
    from agent.specialists_manage import cmd_clear

    code = cmd_clear(console)
    if code:
        raise typer.Exit(code=code)


@specialists_app.command("active")
def specialists_active_cmd():
    """Show the specialist currently active for CLI runs."""
    from agent.specialists_manage import cmd_active

    code = cmd_active(console)
    if code:
        raise typer.Exit(code=code)
