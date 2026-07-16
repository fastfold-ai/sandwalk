"""Helpers backing the startup banner: skill counts, tips, and news lines."""

import random

from cli.constants import _FASTFOLD_CORE_SKILL_NAMES
from ui.terminal import SLASH_COMMANDS


def _installed_claude_skill_names() -> list[str]:
    """Return installed skill names across all tiers (global, project, bundled)."""
    from agent.skills import installed_skill_names

    return installed_skill_names()


def _count_installed_claude_skills() -> int:
    """Count installed agent skills."""
    return len(_installed_claude_skill_names())


def _has_fastfold_skills_installed() -> bool:
    """Return True when at least one official Fastfold skill is installed."""
    from agent.skills import user_installed_skill_names

    installed = set(user_installed_skill_names())
    return bool(installed.intersection(_FASTFOLD_CORE_SKILL_NAMES))


def _get_cached_skills_update_safe() -> dict | None:
    """Local-only cached skills-update check for the banner (never raises)."""
    try:
        from agent.skills import get_cached_skills_update

        return get_cached_skills_update()
    except Exception:
        return None


def _start_skills_update_check() -> None:
    """Refresh the skills-update cache in a daemon thread (no boot-path network)."""
    import threading

    def _worker():
        try:
            from agent.skills import refresh_skills_update_cache

            refresh_skills_update_cache()
        except Exception:
            pass

    try:
        threading.Thread(target=_worker, daemon=True).start()
    except Exception:
        pass


def _get_loaded_tool_count_hint() -> int:
    """Return loaded tool count when already available, else a static hint."""
    from cli.constants import _BANNER_TOOL_COUNT_HINT

    try:
        from tools import registry

        count = len(registry.list_tools())
        if count > 0:
            return count
    except Exception:
        pass
    return _BANNER_TOOL_COUNT_HINT


def _random_command_tip_markup() -> str:
    """Return a random slash-command tip from actual terminal commands."""
    if not SLASH_COMMANDS:
        return "[dim]Tip: use slash commands in interactive mode.[/dim]"

    command, description = random.choice(list(SLASH_COMMANDS.items()))
    return f"[dim]Tip: try [/][bold #D4148E]{command}[/][dim] — {description}[/dim]"


_BOLTZ_NEWS_USE_CASES = (
    "structure and binding",
    "protein design",
    "protein screening",
    "small-molecule design",
    "small-molecule screening",
    "ADME prediction",
)


def _random_news_item_markup() -> str:
    """Return a rotating Boltz API news/action line."""
    installed = set(_installed_claude_skill_names())
    use_case = random.choice(_BOLTZ_NEWS_USE_CASES)
    if "boltz" in installed:
        return (
            "[bold #25C19F]Boltz API skill now available![/] "
            f"[#7A7A7A]· Try: Show me Boltz API examples for {use_case}[/]"
        )
    return (
        "[bold #25C19F]Boltz API skill now available[/] "
        f"[#7A7A7A]· Try: Show me Boltz API examples for {use_case}[/]"
    )
