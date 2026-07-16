"""Startup banner rendering for interactive/batch CLI runs."""

from _version import __version__
from cli.app import BANNER, console
from cli.banner_support import (
    _count_installed_claude_skills,
    _get_cached_skills_update_safe,
    _get_loaded_tool_count_hint,
    _random_command_tip_markup,
    _random_news_item_markup,
)
from cli.subscription import _format_plan_label, _resolve_fastfold_subscription_tier_local
from cli.version_check import _get_cached_upgrade_available_version


def print_banner(cfg=None):
    """Print the startup banner with the sandwalk mark."""
    from rich.padding import Padding
    from rich.table import Table
    from rich.text import Text

    from agent.config import Config

    cfg = cfg or Config.load()
    n_tools = _get_loaded_tool_count_hint()
    n_skills = _count_installed_claude_skills()
    model_raw = str(cfg.get("llm.model") or "").strip()
    model_names = {
        "claude-sonnet-4-5-20250929": "Sonnet 4.5",
        "claude-haiku-4-5-20251001": "Haiku 4.5",
        "claude-opus-4-6": "Opus 4.6",
        "gpt-4o": "GPT-4o",
        "gpt-4o-mini": "GPT-4o Mini",
    }
    model_name = model_names.get(model_raw, model_raw)

    tier = _resolve_fastfold_subscription_tier_local(cfg)
    tier_display = _format_plan_label(tier)
    status_parts: list[str] = []
    if model_name:
        status_parts.append(model_name)
    if tier_display:
        status_parts.append(tier_display)
    status_line = " · ".join(status_parts)
    upgrade_version = _get_cached_upgrade_available_version(__version__)

    # Medium gray — readable on light/dark terminals without competing with meta text.
    logo_text = Text(BANNER.strip("\n"), style="#8B8B8B")
    meta_lines = [
        f"[bold white]sandwalk[/] [dim]v{__version__}[/]",
    ]
    if status_line:
        meta_lines.append(f"[dim]{status_line}[/dim]")
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
    console.print(header)
