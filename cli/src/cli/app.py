"""Shared Typer app, console, and spinner used across all cli command modules."""

from contextlib import contextmanager

import typer
from rich.console import Console

# ─── Startup banner (sandwalk mark — compact 3-bar weave) ───
# Left low → middle high → right low (weave, like the full mark).
BANNER = """

   ██
██ ██ ██
██    ██

"""

app = typer.Typer(
    name="sandwalk",
    help=(
        "sandwalk — a thinking path for open science.\n\n"
        "Common usage:\n"
        '  sandwalk "your research question"\n'
        '  sandwalk --smiles "CCO" "Profile this compound"\n'
        "  sandwalk config show\n"
        "  sandwalk tool list"
    ),
    no_args_is_help=False,
)
console = Console()


@contextmanager
def spinner(message: str, *, console: Console = console):
    """Animated status spinner for long-running operations.

    Renders an animated 'dots' spinner on a TTY; on a non-interactive stream
    Rich falls back to a single static line, so this is always safe to use.
    """
    with console.status(f"[green]{message}[/green]", spinner="dots"):
        yield
