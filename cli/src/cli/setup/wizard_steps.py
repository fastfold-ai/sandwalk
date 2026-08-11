"""CLI-option cleanup, health check, and closing panel for `sandwalk setup`."""

from rich.panel import Panel
from typer.models import OptionInfo

from cli.app import console

_BOOL_FALSE_DEFAULTS = {"set_default_profile", "skip_skills", "skip_datasets", "skip_mcp", "skip_sandbox"}


def _clean_setup_option_defaults(values: dict) -> dict:
    """Replace unresolved Typer OptionInfo defaults with concrete fallbacks.

    setup_cmd is also invoked directly from Python (first-run flows) where
    Typer's argument resolution never runs, leaving OptionInfo objects in place.
    """
    cleaned = {}
    for key, value in values.items():
        if isinstance(value, OptionInfo):
            cleaned[key] = False if key in _BOOL_FALSE_DEFAULTS else None
        else:
            cleaned[key] = value
    return cleaned


def _setup_run_health_check() -> None:
    console.print()
    console.print("  [cyan]Running health check...[/cyan]")
    from agent.config import Config
    from agent.doctor import has_errors, run_checks, to_table

    cfg = Config.load()
    checks = run_checks(cfg)
    console.print(to_table(checks))
    if has_errors(checks):
        console.print(
            "\n  [yellow]Some issues detected.[/yellow] Run `sandwalk doctor` for details."
        )
    else:
        console.print("\n  [green]All checks passed.[/green]")


def _setup_finish(cfg) -> None:
    # Mark UI onboarding complete when CLI setup finishes.
    try:
        cfg.set("ui.onboarding_completed", True)
        cfg.set("ui.onboarding_step", 6)
        cfg.save()
    except Exception:
        pass

    console.print()
    console.print(
        Panel(
            "[bold green]You're all set![/bold green]\n\n"
            "  [cyan]sandwalk[/cyan]                      Interactive mode\n"
            '  [cyan]sandwalk "your question"[/cyan]      Single query\n'
            "  [cyan]sandwalk doctor[/cyan]               Full health check\n"
            "  [cyan]sandwalk keys[/cyan]                 Optional API keys",
            title="[green]Quick Start[/green]",
            border_style="green",
        )
    )
