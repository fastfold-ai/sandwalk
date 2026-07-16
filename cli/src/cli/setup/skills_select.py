"""Skill-catalog selection and the setup wizard's skills-install step."""

import sys

import typer

from cli.app import console, spinner
from cli.setup.skills_install import _install_skill_sources


def _select_skills_from_catalog(catalog: list[dict]) -> list[str]:
    """Let the user pick skills to install from the live catalog. Returns install sources."""
    # Interactive multi-select (questionary) when available.
    if sys.stdin.isatty() and sys.stdout.isatty():
        try:
            import questionary
            from prompt_toolkit.styles import Style

            selector_style = Style.from_dict(
                {
                    "qmark": "fg:#00bcd4 bold",
                    "question": "bold",
                    "answer": "fg:#4caf50 bold",
                    "pointer": "fg:#4caf50",
                    "highlighted": "noreverse bold",
                    "selected": "fg:#4caf50 bold",
                    "instruction": "fg:#858585",
                    "text": "fg:#858585",
                }
            )
            choices = [
                questionary.Choice(
                    title=f"{c['name']} — {(c.get('description') or '').strip()[:80]}",
                    value=c["install_source"],
                    checked=True,
                )
                for c in catalog
            ]
            picked = questionary.checkbox(
                "Select skills to install (all selected by default)",
                choices=choices,
                instruction="(↑/↓ move, space toggle, enter confirm — all preselected)",
                style=selector_style,
                qmark="❯",
                pointer="▸",
            ).ask()
            return list(picked or [])
        except typer.Exit:
            raise
        except Exception:
            pass

    # Inline fallback: numbered list + comma-separated selection.
    console.print("  [cyan]Available skills[/cyan] [dim](all installed by default)[/dim]")
    for idx, c in enumerate(catalog, 1):
        console.print(f"    [{idx}] {c['name']} — [dim]{(c.get('description') or '').strip()[:80]}[/dim]")
    try:
        raw = input("  Select skills (comma-separated numbers, 'all', or 'none'; Enter for all): ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        return []
    if not raw or raw == "all":
        return [c["install_source"] for c in catalog]
    if raw == "none":
        return []
    sources: list[str] = []
    for token in raw.split(","):
        token = token.strip()
        if token.isdigit() and 1 <= int(token) <= len(catalog):
            sources.append(catalog[int(token) - 1]["install_source"])
    return sources


def _select_suggested_sources() -> list[str]:
    """Offer curated third-party skill collections (grouped by provider). Returns install sources."""
    from agent.skills import SUGGESTED_SKILL_SOURCES

    if not SUGGESTED_SKILL_SOURCES:
        return []

    if sys.stdin.isatty() and sys.stdout.isatty():
        try:
            import questionary
            from prompt_toolkit.styles import Style

            selector_style = Style.from_dict(
                {
                    "qmark": "fg:#00bcd4 bold",
                    "question": "bold",
                    "answer": "fg:#4caf50 bold",
                    "pointer": "fg:#4caf50",
                    "highlighted": "noreverse bold",
                    "selected": "fg:#4caf50 bold",
                    "instruction": "fg:#858585",
                    "text": "fg:#858585",
                }
            )
            choices = [
                questionary.Choice(
                    title=f"{s['provider']} — {s['description']} ({s['source']})",
                    value=s["source"],
                )
                for s in SUGGESTED_SKILL_SOURCES
            ]
            picked = questionary.checkbox(
                "Suggested community skill collections (optional)",
                choices=choices,
                instruction="(↑/↓ move, space toggle, enter confirm; installs the whole collection)",
                style=selector_style,
                qmark="❯",
                pointer="▸",
            ).ask()
            return list(picked or [])
        except typer.Exit:
            raise
        except Exception:
            pass

    console.print("  [cyan]Suggested community skill collections[/cyan] [dim](installs the whole collection)[/dim]")
    for idx, s in enumerate(SUGGESTED_SKILL_SOURCES, 1):
        console.print(f"    [{idx}] {s['provider']} — [dim]{s['description']} ({s['source']})[/dim]")
    try:
        raw = input("  Select collections (comma-separated numbers, or 'all'; Enter to skip): ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        return []
    if not raw:
        return []
    if raw == "all":
        return [s["source"] for s in SUGGESTED_SKILL_SOURCES]
    sources: list[str] = []
    for token in raw.split(","):
        token = token.strip()
        if token.isdigit() and 1 <= int(token) <= len(SUGGESTED_SKILL_SOURCES):
            sources.append(SUGGESTED_SKILL_SOURCES[int(token) - 1]["source"])
    return sources


