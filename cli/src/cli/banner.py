"""Startup banner rendering for interactive/batch CLI runs."""

from _version import __version__
from cli.app import BANNER
from cli.app import console as _app_console
from cli.banner_support import (
    _count_installed_claude_skills,
    _get_cached_skills_update_safe,
    _get_loaded_tool_count_hint,
    _random_command_tip_markup,
    _random_news_item_markup,
    banner_model_provider_markup,
)
from cli.subscription import _format_plan_label, _resolve_fastfold_subscription_tier_local
from cli.version_check import _get_cached_upgrade_available_version

# Re-export for tests that monkeypatch ``cli.banner.console``.
console = _app_console


def print_banner(cfg=None, *, console=None):
    """Print the startup banner with the sandwalk mark.

    ``console`` defaults to the shared CLI console; pass a capture Console
    (e.g. StringIO-backed) to render into the owned transcript instead.
    """
    from rich.padding import Padding
    from rich.table import Table
    from rich.text import Text

    from agent.config import Config

    # Prefer explicit console; else module ``console`` (tests monkeypatch it).
    out = console if console is not None else globals()["console"]
    cfg = cfg or Config.load()
    n_tools = _get_loaded_tool_count_hint()
    n_skills = _count_installed_claude_skills()
    # Same model + muted provider styling as the compose meta row.
    model_status = banner_model_provider_markup(cfg)

    tier = _resolve_fastfold_subscription_tier_local(cfg)
    tier_display = _format_plan_label(tier)
    upgrade_version = _get_cached_upgrade_available_version(__version__)

    # Medium gray — readable on light/dark terminals without competing with meta text.
    logo_text = Text(BANNER.strip("\n"), style="#8B8B8B")
    meta_lines = [
        f"[bold white]sandwalk[/] [dim]v{__version__}[/]",
    ]
    if model_status:
        if tier_display:
            meta_lines.append(f"{model_status} [#8a8f98]· {tier_display}[/]")
        else:
            meta_lines.append(model_status)
    elif tier_display:
        meta_lines.append(f"[dim]{tier_display}[/dim]")
    if upgrade_version:
        meta_lines.append(
            f"[bold yellow]Upgrade available:[/] [dim]v{__version__} -> v{upgrade_version}[/dim] "
            "[dim]Run [/dim][bold #D4148E]/upgrade[/]"
        )
    skills_update = _get_cached_skills_update_safe()
    if skills_update:
        meta_lines.append(
            f"[bold yellow]Skills update available:[/] "
            f"[dim]{skills_update['installed']} -> {skills_update['latest']}[/dim] "
            "[dim]Run [/dim][bold #D4148E]/skills-upgrade[/]"
        )
    meta_lines.append(f"[dim]{n_tools} tools · {n_skills} skills[/dim]")
    meta_lines.append(_random_command_tip_markup())
    meta_lines.append(_random_news_item_markup())
    meta_text = Text.from_markup("\n".join(meta_lines))

    header = Table.grid(padding=(0, 2))
    header.add_column(no_wrap=True)
    header.add_column()
    # Nudge mark down so it sits nearer the vertical center of the meta block.
    header.add_row(Padding(logo_text, (1, 0, 0, 0)), Padding(meta_text, (0, 0, 0, 1)))
    # Extra inset so the mark isn't flush against the terminal / transcript edge.
    out.print()
    out.print(Padding(header, (1, 3, 1, 3)))
    out.print()


def render_banner_ansi(cfg=None, *, width: int = 100) -> str:
    """Render the startup banner to an ANSI string for the transcript panel."""
    from io import StringIO

    from rich.console import Console

    buf = StringIO()
    capture = Console(
        file=buf,
        width=max(40, int(width or 100)),
        force_terminal=True,
        color_system="256",
        highlight=False,
    )
    print_banner(cfg, console=capture)
    return buf.getvalue().rstrip("\n")
