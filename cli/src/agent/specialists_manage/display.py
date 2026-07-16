"""Read-only specialist display commands: list, show, active."""

from __future__ import annotations

from rich.console import Console
from rich.table import Table

from agent_server.models import Specialist

from .state import _store, get_active_specialist, resolve_specialist_ref


def _print_specialist(console: Console, specialist: Specialist) -> None:
    console.print(f"  [bold]{specialist.name}[/bold]  [dim]{specialist.slug}[/dim]")
    console.print(f"  [dim]id[/dim] {specialist.id}")
    if specialist.description:
        console.print(f"  {specialist.description}")
    console.print(
        f"  [dim]color[/dim] {specialist.color}  [dim]icon[/dim] {specialist.icon}"
    )
    skills = ", ".join(specialist.skill_names) if specialist.skill_names else "(none)"
    mcps = ", ".join(specialist.mcp_server_ids) if specialist.mcp_server_ids else "(none)"
    catalogs = (
        ", ".join(specialist.mcp_catalog_ids)
        if getattr(specialist, "mcp_catalog_ids", None)
        else "(none)"
    )
    console.print(f"  [dim]skills[/dim] {skills}")
    console.print(f"  [dim]mcps[/dim] {mcps}")
    console.print(f"  [dim]mcp catalogs[/dim] {catalogs}")
    if specialist.instructions:
        console.print("  [dim]instructions[/dim]")
        for line in specialist.instructions.strip().splitlines():
            console.print(f"    {line}")


def cmd_list(console: Console) -> int:
    store = _store()
    specialists = store.list_specialists()
    active = get_active_specialist(store=store)
    if not specialists:
        console.print("[yellow]No specialists yet.[/yellow]")
        console.print(
            "  [dim]Create one with[/dim] fastfold specialists create \"Name\" "
            "[dim]or Dashboard → Specialists[/dim]"
        )
        return 0
    table = Table(
        title=f"Specialists ({len(specialists)})",
        show_lines=False,
    )
    table.add_column("Active", style="dim", no_wrap=True)
    table.add_column("Name", style="bold cyan", no_wrap=True)
    table.add_column("Slug", style="dim", no_wrap=True)
    table.add_column("Skills", style="dim", justify="right")
    table.add_column("MCPs", style="dim", justify="right")
    table.add_column("Description", style="white")
    for item in specialists:
        is_active = active is not None and active.id == item.id
        mcp_count = len(item.mcp_server_ids or []) + len(
            getattr(item, "mcp_catalog_ids", None) or []
        )
        table.add_row(
            "●" if is_active else "",
            item.name,
            item.slug,
            str(len(item.skill_names or [])),
            str(mcp_count),
            (item.description or "").strip() or "—",
        )
    console.print(table)
    if active:
        console.print(
            f"  [dim]CLI active:[/dim] [bold]{active.name}[/bold] "
            f"[dim]({active.slug})[/dim]"
        )
    else:
        console.print("  [dim]CLI active: none (global skills/MCPs)[/dim]")
    console.print(
        "  [dim]Set:[/dim] /specialist use <slug>  "
        "[dim]or[/dim] /specialist <slug>  "
        "[dim]· Clear:[/dim] /specialist clear"
    )
    return 0


def cmd_show(console: Console, ref: str) -> int:
    specialist = resolve_specialist_ref(ref)
    if specialist is None:
        console.print(f"  [yellow]Specialist not found:[/yellow] {ref}")
        return 1
    _print_specialist(console, specialist)
    active = get_active_specialist()
    if active and active.id == specialist.id:
        console.print("  [green]Currently active for CLI runs.[/green]")
    return 0


def cmd_active(console: Console) -> int:
    specialist = get_active_specialist()
    if specialist is None:
        console.print("  [dim]No active specialist (global skills/MCPs).[/dim]")
        return 0
    console.print("  [dim]Active for CLI:[/dim]")
    _print_specialist(console, specialist)
    return 0
