"""Setup wizard step: install agent skills from the catalog or custom sources."""

import sys

import typer

from cli.app import console, spinner
from cli.setup.skills_install import _install_skill_sources
from cli.setup.skills_select import _select_skills_from_catalog, _select_suggested_sources


def _prompt_install_skills(skills_arg: str | None = None, skip: bool = False) -> None:
    """Setup step: install agent skills from the live Fastfold catalog or custom sources."""
    from agent.skills import discover_skills

    if skip:
        return

    # Non-interactive explicit list (CI/scripting): `--skills a,b,owner/repo@path`
    if skills_arg:
        sources = [s.strip() for s in skills_arg.split(",") if s.strip()]
        if sources:
            console.print("\n  [cyan]Agent skills[/cyan]")
            _install_skill_sources(sources)
        return

    interactive = sys.stdin.isatty() and sys.stdout.isatty()
    if not interactive:
        console.print(
            "\n  [dim]Skipping skills install (non-interactive). "
            "Add later with `sandwalk skills find` / `sandwalk skills add <source>`.[/dim]"
        )
        return

    console.print("\n  [cyan]Agent skills[/cyan]")
    console.print(
        "  [dim]Skills add guided workflows (folding, MD, protein design, reporting). "
        "They are optional and installed on demand.[/dim]"
    )
    try:
        proceed = input("  Install agent skills now? [Y/n] ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        console.print("\n  [dim]Setup cancelled.[/dim]")
        raise typer.Exit()
    if proceed in ("n", "no"):
        console.print(
            "  [dim]Skipped. Add later with `sandwalk skills find` / `sandwalk skills add <source>`.[/dim]"
        )
        return

    with spinner("Fetching the current Fastfold skills catalog..."):
        catalog = discover_skills()
    selected: list[str] = []
    if catalog:
        selected = _select_skills_from_catalog(catalog)
    else:
        console.print(
            "  [yellow]Could not fetch the catalog[/yellow] [dim](needs git + network). "
            "You can still add suggested or custom sources below.[/dim]"
        )

    # Offer curated third-party collections (K-Dense-AI, Anthropic, DeepMind).
    selected += _select_suggested_sources()

    # Always offer custom sources (GitHub URL / owner/repo@subpath / local path).
    try:
        custom = input(
            "  Add custom skill source(s)? (GitHub URL or owner/repo@path, comma-separated; Enter to skip): "
        ).strip()
    except (EOFError, KeyboardInterrupt):
        custom = ""
    if custom:
        selected += [s.strip() for s in custom.split(",") if s.strip()]

    if not selected:
        console.print("  [dim]No skills selected.[/dim]")
        return

    _install_skill_sources(selected)
