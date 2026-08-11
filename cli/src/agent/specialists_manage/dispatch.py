"""Interactive `/specialist ...` argv dispatch."""

from __future__ import annotations

from rich.console import Console

from .crud import cmd_clear, cmd_create, cmd_delete, cmd_use
from .display import cmd_active, cmd_list, cmd_show
from .state import resolve_specialist_ref


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
