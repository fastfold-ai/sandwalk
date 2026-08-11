"""`sandwalk skills` — manage and inspect agent skills (list/enable/disable/add)."""

import typer
from rich.table import Table

from cli.app import app, console
from cli.setup.skills_install import _provider_label_for_source

skill_app = typer.Typer(help="Manage and inspect agent skills")
app.add_typer(skill_app, name="skills")
app.add_typer(skill_app, name="skill")  # back-compat alias


@skill_app.command("list")
def skill_list():
    """List all loaded agent skills."""
    from agent.skills import display_author, display_updated, display_version, list_skills

    skills = list_skills()
    if not skills:
        console.print("[yellow]No skills loaded.[/yellow]")
        raise typer.Exit()

    enabled_count = len([info for info in skills if getattr(info, "enabled", True)])
    table = Table(
        title=f"Agent Skills ({len(skills)} total, {enabled_count} enabled)",
        show_lines=False,
    )
    table.add_column("Skill", style="bold cyan", no_wrap=True)
    table.add_column("Enabled", style="dim", no_wrap=True)
    table.add_column("Source", style="dim")
    table.add_column("Author", style="dim")
    table.add_column("Updated", style="dim")
    table.add_column("Version", style="dim")
    table.add_column("Description", style="white")

    for info in skills:
        table.add_row(
            info.name,
            "yes" if getattr(info, "enabled", True) else "no",
            info.source,
            display_author(info),
            display_updated(info),
            display_version(info),
            info.description,
        )

    console.print(table)


@skill_app.command("enable")
def skill_enable(
    name: str = typer.Argument(..., help="Installed skill name to enable"),
):
    """Enable a skill without uninstalling it."""
    from agent.skills import set_skill_enabled

    result = set_skill_enabled(name, True)
    if result.get("ok"):
        console.print(f"  [green]{result['summary']}[/green]")
    else:
        console.print(f"  [yellow]{result['summary']}[/yellow]")
        raise typer.Exit(code=1)


@skill_app.command("disable")
def skill_disable(
    name: str = typer.Argument(..., help="Installed skill name to disable"),
):
    """Disable a skill without uninstalling it."""
    from agent.skills import set_skill_enabled

    result = set_skill_enabled(name, False)
    if result.get("ok"):
        console.print(f"  [green]{result['summary']}[/green]")
    else:
        console.print(f"  [yellow]{result['summary']}[/yellow]")
        raise typer.Exit(code=1)


@skill_app.command("add")
def skill_add(
    source: str = typer.Argument(
        ..., help="GitHub URL, owner/repo@subpath, local path, or catalog name"
    ),
):
    """Install an agent skill from GitHub, a local path, or the catalog."""
    from agent.skills import install_skill

    provider = _provider_label_for_source(source)
    with console.status(
        f"[green]Installing skill from {source} ({provider})...[/green]", spinner="dots"
    ):
        result = install_skill(source)
    method = {"npx": "npx skills add", "git": "git", "local": "local copy"}.get(result.get("via", ""), result.get("via", "?"))
    if result.get("ok"):
        console.print(f"  [green]{result['summary']}[/green] [dim](provider: {provider}, method: {method})[/dim]")
    else:
        console.print(f"  [red]{result['summary']}[/red]")
        raise typer.Exit(code=1)


@skill_app.command("install")
def skill_install(
    source: str = typer.Argument(..., help="GitHub URL, owner/repo@subpath, local path, or name"),
):
    """Alias for `skills add`."""
    skill_add(source)


# ─── Top-level `add` group (alias: `sandwalk add skill <source>`) ─────────────
add_app = typer.Typer(help="Add skills and other resources")
app.add_typer(add_app, name="add")


@add_app.command("skills")
def add_skills_cmd(
    source: str = typer.Argument(..., help="GitHub URL, owner/repo@subpath, local path, or name"),
):
    """Install an agent skill (alias for ``sandwalk skills add``)."""
    skill_add(source)


@add_app.command("skill", hidden=True)
def add_skill_cmd(
    source: str = typer.Argument(..., help="GitHub URL, owner/repo@subpath, local path, or name"),
):
    """Back-compat alias for `sandwalk add skills`."""
    skill_add(source)
