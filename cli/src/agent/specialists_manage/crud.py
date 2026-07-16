"""Mutating specialist commands: create, update, delete, use, clear."""

from __future__ import annotations

from rich.console import Console

from .state import (
    _store,
    get_active_specialist_ref,
    resolve_specialist_ref,
    set_active_specialist_ref,
)


def cmd_create(
    console: Console,
    *,
    name: str,
    slug: str | None = None,
    description: str | None = None,
    instructions: str | None = None,
    color: str = "ink",
    icon: str = "agent",
    skills: list[str] | None = None,
    mcps: list[str] | None = None,
    use: bool = False,
) -> int:
    try:
        specialist = _store().create_specialist(
            name=name,
            slug=slug,
            description=description,
            instructions=instructions,
            color=color,
            icon=icon,
            skill_names=skills,
            mcp_server_ids=mcps,
        )
    except ValueError as exc:
        console.print(f"  [red]{exc}[/red]")
        return 1
    console.print(
        f"  [green]Created specialist[/green] [bold]{specialist.name}[/bold] "
        f"[dim]({specialist.slug})[/dim]"
    )
    if use:
        set_active_specialist_ref(specialist.slug)
        console.print("  [green]Set as active for CLI runs.[/green]")
    return 0


def cmd_update(
    console: Console,
    ref: str,
    *,
    name: str | None = None,
    slug: str | None = None,
    description: str | None = None,
    clear_description: bool = False,
    instructions: str | None = None,
    clear_instructions: bool = False,
    color: str | None = None,
    icon: str | None = None,
    skills: list[str] | None = None,
    mcps: list[str] | None = None,
) -> int:
    store = _store()
    current = resolve_specialist_ref(ref, store)
    if current is None:
        console.print(f"  [yellow]Specialist not found:[/yellow] {ref}")
        return 1
    try:
        specialist = store.update_specialist(
            current.id,
            name=name,
            slug=slug,
            description=description,
            update_description=clear_description or description is not None,
            instructions=instructions,
            update_instructions=clear_instructions or instructions is not None,
            color=color,
            icon=icon,
            skill_names=skills,
            mcp_server_ids=mcps,
        )
    except ValueError as exc:
        console.print(f"  [red]{exc}[/red]")
        return 1
    if specialist is None:
        console.print(f"  [yellow]Specialist not found:[/yellow] {ref}")
        return 1
    console.print(
        f"  [green]Updated[/green] [bold]{specialist.name}[/bold] "
        f"[dim]({specialist.slug})[/dim]"
    )
    return 0


def cmd_delete(console: Console, ref: str) -> int:
    store = _store()
    specialist = resolve_specialist_ref(ref, store)
    if specialist is None:
        console.print(f"  [yellow]Specialist not found:[/yellow] {ref}")
        return 1
    active_ref = get_active_specialist_ref()
    was_active = False
    if active_ref:
        active = resolve_specialist_ref(active_ref, store)
        was_active = active is not None and active.id == specialist.id
    store.delete_specialist(specialist.id)
    if was_active:
        set_active_specialist_ref(None)
    console.print(
        f"  [green]Deleted[/green] [bold]{specialist.name}[/bold] "
        f"[dim]({specialist.slug})[/dim]"
    )
    return 0


def cmd_use(console: Console, ref: str) -> int:
    specialist = resolve_specialist_ref(ref)
    if specialist is None:
        console.print(f"  [yellow]Specialist not found:[/yellow] {ref}")
        return 1
    if getattr(specialist, "enabled", True) is False:
        console.print(
            f"  [yellow]Specialist is disabled:[/yellow] {specialist.name} "
            f"[dim]({specialist.slug})[/dim]"
        )
        console.print("  [dim]Enable it in Dashboard → Specialists, then try again.[/dim]")
        return 1
    set_active_specialist_ref(specialist.slug)
    console.print(
        f"  [green]Active specialist[/green] [bold]{specialist.name}[/bold] "
        f"[dim]({specialist.slug})[/dim]"
    )
    console.print(
        "  [dim]CLI runs will use only this specialist's skills, MCPs, and instructions.[/dim]"
    )
    return 0


def cmd_clear(console: Console) -> int:
    set_active_specialist_ref(None)
    console.print("  [green]Cleared active specialist.[/green] Using global skills/MCPs.")
    return 0
