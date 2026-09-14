"""Shared Typer app, console, and spinner used across all cli command modules."""

from contextlib import contextmanager

import typer
from rich.console import Console

from ui.markdown.theme import markdown_rich_theme

# ─── Startup banner (sandwalk mark — compact 3-bar weave) ───
# Left low -> middle high -> right low (weave, like the full mark).
BANNER = """

   ██
██ ██ ██
██    ██

"""

# Global offline mode flag
_offline_mode = False


def get_offline_mode() -> bool:
    """Get the global offline mode flag."""
    return _offline_mode


def set_offline_mode(value: bool) -> None:
    """Set the global offline mode flag."""
    global _offline_mode
    _offline_mode = value


app = typer.Typer(
    name="sandwalk",
    help=(
        "sandwalk - a thinking path for open science.\n\n"
        "Common usage:\n"
        '  sandwalk "your research question"\n'
        '  sandwalk --smiles "CCO" "Profile this compound"\n'
        "  sandwalk config show\n"
        "  sandwalk tool list\n"
        "  sandwalk --offline run        # Force offline mode"
    ),
    no_args_is_help=False,
    add_completion=False,
)

console = Console(theme=markdown_rich_theme())


@contextmanager
def spinner(message: str, *, console: Console = console):
    """Animated status spinner for long-running operations.

    Renders an animated 'dots' spinner on a TTY; on a non-interactive stream
    Rich falls back to a single static line, so this is always safe to use.
    """
    with console.status(f"[green]{message}[/green]", spinner="dots"):
        yield
