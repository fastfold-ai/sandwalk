"""`sandwalk skills` — upgrade/remove/delete/find/info subcommands."""

import typer
from rich.table import Table

from cli.app import console, spinner
from cli.skills import skill_app


@skill_app.command("upgrade")
def skill_upgrade(
    catalog_only: bool = typer.Option(
        False, "--catalog-only", help="Only sync the Fastfold catalog (skip other installed sources)"
    ),
    no_catalog: bool = typer.Option(
        False, "--no-catalog", help="Only update already-installed skills (skip catalog sync)"
    ),
    no_npx: bool = typer.Option(
        False, "--no-npx", help="Skip re-syncing npx-installed (project-local) skills"
    ),
):
    """Sync skills: refresh the Fastfold catalog (add new + update) and re-install tracked skills."""
    from agent.skills import GLOBAL_SKILLS_DIR, upgrade_skills

    if catalog_only and no_catalog:
        console.print("  [red]--catalog-only and --no-catalog are mutually exclusive.[/red]")
        raise typer.Exit(code=2)

    if catalog_only:
        # Catalog sync only.
        from agent.skills import DEFAULT_CATALOG, install_skill

        with console.status("[green]Syncing Fastfold catalog...[/green]", spinner="dots"):
            result = install_skill(DEFAULT_CATALOG.split("@", 1)[0])
        if result.get("ok"):
            console.print(f"  [green]{result['summary']}[/green]")
        else:
            console.print(f"  [red]{result['summary']}[/red]")
            raise typer.Exit(code=1)
        return

    with console.status("[green]Syncing agent skills...[/green]", spinner="dots") as status:
        result = upgrade_skills(
            include_catalog=not no_catalog,
            include_npx=not no_npx,
            progress=lambda msg: status.update(f"[green]{msg}[/green]"),
        )
    if result["added"]:
        console.print(f"  [green]Added:[/green] {', '.join(result['added'])}")
    if result["updated"]:
        console.print(f"  [green]Updated:[/green] {', '.join(result['updated'])}")
    if result.get("npx_synced"):
        console.print(f"  [green]npx-synced:[/green] {result['npx_synced']} project-local source(s)")
    if result["failed"]:
        for source, reason in result["failed"]:
            console.print(f"  [yellow]Failed:[/yellow] {source} — {reason}")
    console.print(f"  [dim]{result['summary']}[/dim]")
    console.print(f"  [dim]Location: {GLOBAL_SKILLS_DIR}[/dim]")


@skill_app.command("remove")
def skill_remove(
    name: str = typer.Argument(..., help="Installed skill name to remove"),
):
    """Remove a globally-installed agent skill."""
    from agent.skills import remove_skill

    result = remove_skill(name)
    if result.get("ok"):
        console.print(f"  [green]{result['summary']}[/green]")
    else:
        console.print(f"  [yellow]{result['summary']}[/yellow]")
        raise typer.Exit(code=1)


@skill_app.command("delete")
def skill_delete(
    name: str | None = typer.Argument(None, help="Skill name to delete (omit when using --all)"),
    all_skills: bool = typer.Option(False, "--all", help="Delete ALL user-installed skills"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip the confirmation prompt"),
):
    """Delete a skill, or all user-installed skills with --all (asks to confirm first)."""
    from agent.skills import remove_all_skills, remove_skill, user_installed_skill_names

    if not all_skills:
        if not name:
            console.print("  [yellow]Specify a skill name, or use --all to remove everything.[/yellow]")
            raise typer.Exit(code=2)
        result = remove_skill(name)
        style = "green" if result.get("ok") else "yellow"
        console.print(f"  [{style}]{result['summary']}[/{style}]")
        if not result.get("ok"):
            raise typer.Exit(code=1)
        return

    names = user_installed_skill_names()
    if not names:
        console.print("  [dim]No user-installed skills to delete.[/dim] [dim](Bundled skills are kept.)[/dim]")
        return

    console.print(
        f"  [yellow]This will remove {len(names)} user-installed skill(s):[/yellow] {', '.join(names)}"
    )
    console.print("  [dim]Bundled skills (skill_find, skill_creator) are not affected.[/dim]")
    if not yes:
        try:
            confirm = input("  Delete ALL of these skills? [y/N] ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            console.print("\n  [dim]Cancelled.[/dim]")
            raise typer.Exit()
        if confirm not in ("y", "yes"):
            console.print("  [dim]Cancelled.[/dim]")
            return

    result = remove_all_skills()
    console.print(f"  [green]{result['summary']}[/green]")
    if result.get("removed"):
        console.print(f"  [dim]Removed: {', '.join(result['removed'])}[/dim]")


@skill_app.command("find")
def skill_find(
    query: str | None = typer.Argument(None, help="Optional search query"),
):
    """Discover installable skills from the catalog."""
    from agent.skills import discover_skills

    with spinner("Searching skill catalog..."):
        results = discover_skills(query)
    if not results:
        console.print(
            "  [yellow]No matching skills found.[/yellow] "
            "[dim](Requires git; check network/catalog access.)[/dim]"
        )
        raise typer.Exit()

    table = Table(title=f"Available Skills ({len(results)})", show_lines=False)
    table.add_column("Skill", style="bold cyan", no_wrap=True)
    table.add_column("Install source", style="dim")
    table.add_column("Description", style="white")
    for r in results:
        table.add_row(r["name"], r["install_source"], r["description"])
    console.print(table)
    console.print("  [dim]Install with:[/dim] sandwalk skills add <install source>")


@skill_app.command("info")
def skill_info_cmd(
    name: str = typer.Argument(..., help="Skill name"),
):
    """Show details for an installed skill."""
    from agent.skills import skill_info

    info = skill_info(name)
    if not info:
        console.print(f"  [yellow]Skill '{name}' is not installed.[/yellow]")
        raise typer.Exit(code=1)
    console.print(f"  [bold cyan]{info.name}[/bold cyan] [dim]({info.source})[/dim]")
    if info.description:
        console.print(f"  {info.description}")
    if info.tags:
        console.print(f"  [dim]tags:[/dim] {', '.join(info.tags)}")
    if info.path:
        console.print(f"  [dim]path:[/dim] {info.path}")
