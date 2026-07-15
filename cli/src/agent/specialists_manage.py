"""Shared specialists helpers for `sandwalk specialists` and interactive `/specialist`."""

from __future__ import annotations

from typing import Any

from rich.console import Console
from rich.table import Table

from agent.config import Config
from agent_server.models import Specialist
from agent_server.store import AgentStore

CLI_SPECIALIST_CONFIG_KEY = "agent.cli_specialist"


def _store() -> AgentStore:
    return AgentStore()


def resolve_specialist_ref(ref: str, store: AgentStore | None = None) -> Specialist | None:
    return (store or _store()).resolve_specialist_ref(ref)


def get_active_specialist_ref(config: Config | None = None) -> str | None:
    cfg = config or Config.load()
    value = str(cfg.get(CLI_SPECIALIST_CONFIG_KEY, "") or "").strip()
    return value or None


def set_active_specialist_ref(ref: str | None, config: Config | None = None) -> None:
    cfg = config or Config.load()
    if ref and str(ref).strip():
        cfg.set(CLI_SPECIALIST_CONFIG_KEY, str(ref).strip())
    else:
        cfg.set(CLI_SPECIALIST_CONFIG_KEY, "")
    cfg.save()


def get_active_specialist(
    config: Config | None = None,
    store: AgentStore | None = None,
) -> Specialist | None:
    ref = get_active_specialist_ref(config)
    if not ref:
        return None
    return resolve_specialist_ref(ref, store)


def apply_specialist_to_context(
    context: dict[str, Any] | None,
    specialist: Specialist | None,
    *,
    store: AgentStore | None = None,
) -> dict[str, Any]:
    """Mutate/return run context with specialist instructions, skills, and MCPs."""
    ctx = dict(context or {})
    if specialist is None:
        ctx.pop("specialist_instructions", None)
        ctx.pop("allowed_skill_names", None)
        # Leave mcp_servers alone when clearing — caller may have set globals.
        return ctx

    instructions = (specialist.instructions or "").strip()
    if instructions:
        ctx["specialist_instructions"] = instructions
    else:
        ctx.pop("specialist_instructions", None)

    ctx["allowed_skill_names"] = list(specialist.skill_names or [])

    from agent_server.default_specialists import filter_mcp_servers_for_specialist
    from agent_server.mcp_service import McpService

    agent_store = store or _store()
    servers = McpService(agent_store).resolve_runtime_servers()
    ctx["mcp_servers"] = filter_mcp_servers_for_specialist(
        servers,
        mcp_server_ids=list(specialist.mcp_server_ids or []),
        mcp_catalog_ids=list(getattr(specialist, "mcp_catalog_ids", None) or []),
    )
    return ctx


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


def cmd_active(console: Console) -> int:
    specialist = get_active_specialist()
    if specialist is None:
        console.print("  [dim]No active specialist (global skills/MCPs).[/dim]")
        return 0
    console.print("  [dim]Active for CLI:[/dim]")
    _print_specialist(console, specialist)
    return 0


def handle_specialist_argv(argv: list[str], console: Console) -> int:
    """Dispatch interactive `/specialist ...` argv (without the leading command)."""
    parts = [part for part in argv if part]
    if not parts:
        return cmd_list(console)
    action = parts[0].lower()
    rest = parts[1:]
    if action in {"list", "ls"}:
        return cmd_list(console)
    if action in {"active", "status"}:
        return cmd_active(console)
    if action in {"show", "get", "info"}:
        if not rest:
            console.print("  [yellow]Usage:[/yellow] /specialist show <slug|name|id>")
            return 1
        return cmd_show(console, " ".join(rest))
    if action in {"use", "enable", "set"}:
        if not rest:
            console.print("  [yellow]Usage:[/yellow] /specialist use <slug|name|id>")
            return 1
        return cmd_use(console, " ".join(rest))
    if action in {"clear", "none", "disable", "unset"}:
        return cmd_clear(console)
    if action in {"delete", "rm", "remove"}:
        if not rest:
            console.print("  [yellow]Usage:[/yellow] /specialist delete <slug|name|id>")
            return 1
        return cmd_delete(console, " ".join(rest))
    if action in {"create", "add", "new"}:
        if not rest:
            console.print(
                '  [yellow]Usage:[/yellow] /specialist create "Name" '
                "[--slug s] [--instructions text]"
            )
            return 1
        name = " ".join(rest).strip().strip('"').strip("'")
        if not name:
            console.print("  [yellow]Name is required.[/yellow]")
            return 1
        return cmd_create(console, name=name)
    # Bare ref → activate for CLI runs (discoverable set path).
    specialist = resolve_specialist_ref(action if not rest else " ".join(parts))
    if specialist is not None:
        return cmd_use(console, specialist.slug)
    console.print(
        "  [yellow]Unknown specialist command.[/yellow] "
        "Try /specialist <slug> | list | show | use | clear | create | delete | active"
    )
    return 1
