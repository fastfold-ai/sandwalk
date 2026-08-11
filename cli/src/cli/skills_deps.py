"""`sandwalk skills deps` — install/check runtime skill dependencies."""

from __future__ import annotations

import typer
from rich.table import Table

from cli.app import console
from cli.skills import skill_app

deps_app = typer.Typer(
    help="Install and check runtime dependencies for skills that need extras"
)
skill_app.add_typer(deps_app, name="deps")


def _print_status(status) -> None:
    color = {"ok": "green", "missing": "yellow", "error": "red"}.get(
        status.status, "white"
    )
    console.print(
        f"  [{color}]{status.skill_name}[/{color}] "
        f"[dim]({status.adapter_id})[/dim] — {status.summary}"
    )
    if status.command:
        console.print(f"  [dim]command:[/dim] {status.command}")
    if not status.checks:
        return
    table = Table(show_header=True, show_lines=False, box=None, padding=(0, 1))
    table.add_column("Check", style="cyan", no_wrap=True)
    table.add_column("Status", no_wrap=True)
    table.add_column("Detail")
    for check in status.checks:
        st = check.status
        style = {"ok": "green", "missing": "yellow", "error": "red", "warn": "yellow"}.get(
            st, "white"
        )
        detail = check.detail
        if check.fix and st != "ok":
            detail = f"{detail}  (fix: {check.fix})"
        table.add_row(check.name, f"[{style}]{st}[/{style}]", detail)
    console.print(table)


@deps_app.command("status")
def deps_status(
    name: str | None = typer.Argument(
        None, help="Skill name or adapter id (omit to list all)"
    ),
):
    """Show runtime dependency status for registered skill adapters."""
    from agent.skills.deps import status_for

    try:
        rows = status_for(name)
    except LookupError as exc:
        console.print(f"  [yellow]{exc}[/yellow]")
        raise typer.Exit(code=1) from exc
    if not rows:
        console.print("[yellow]No skill runtime dependency adapters registered.[/yellow]")
        raise typer.Exit()
    for status in rows:
        _print_status(status)
        console.print()


@deps_app.command("install")
def deps_install(
    name: str = typer.Argument(..., help="Skill name or adapter id"),
):
    """Install runtime dependencies for a skill."""
    from agent.skills.deps import install_skill_deps

    with console.status(
        f"[green]Installing runtime deps for {name}...[/green]", spinner="dots"
    ):
        try:
            result = install_skill_deps(name, force=False)
        except LookupError as exc:
            console.print(f"  [yellow]{exc}[/yellow]")
            raise typer.Exit(code=1) from exc
    if result.ok:
        console.print(f"  [green]{result.summary}[/green]")
    else:
        console.print(f"  [red]{result.summary}[/red]")
        if result.status is not None:
            _print_status(result.status)
        raise typer.Exit(code=1)
    if result.status is not None:
        _print_status(result.status)


@deps_app.command("reinstall")
def deps_reinstall(
    name: str = typer.Argument(..., help="Skill name or adapter id"),
):
    """Force-reinstall runtime dependencies for a skill."""
    from agent.skills.deps import install_skill_deps

    with console.status(
        f"[green]Reinstalling runtime deps for {name}...[/green]", spinner="dots"
    ):
        try:
            result = install_skill_deps(name, force=True)
        except LookupError as exc:
            console.print(f"  [yellow]{exc}[/yellow]")
            raise typer.Exit(code=1) from exc
    if result.ok:
        console.print(f"  [green]{result.summary}[/green]")
    else:
        console.print(f"  [red]{result.summary}[/red]")
        if result.status is not None:
            _print_status(result.status)
        raise typer.Exit(code=1)
    if result.status is not None:
        _print_status(result.status)


@deps_app.command("doctor")
def deps_doctor(
    name: str | None = typer.Argument(
        None, help="Skill name or adapter id (omit to check all)"
    ),
):
    """Run health checks for skill runtime dependencies."""
    from agent.skills.deps import status_for

    try:
        rows = status_for(name)
    except LookupError as exc:
        console.print(f"  [yellow]{exc}[/yellow]")
        raise typer.Exit(code=1) from exc
    failed = False
    for status in rows:
        _print_status(status)
        console.print()
        if status.status != "ok":
            failed = True
    if failed:
        raise typer.Exit(code=1)
