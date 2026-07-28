"""Startup banner for the Sandwalk agent server."""

from __future__ import annotations

from pathlib import Path

from rich.console import Console
from rich.padding import Padding
from rich.table import Table
from rich.text import Text

from _version import __version__
from cli.app import BANNER


def print_server_banner(
    *,
    host: str,
    port: int,
    public: bool,
    auth_enabled: bool,
    uds: Path | None = None,
    ui_available: bool = False,
    console: Console | None = None,
) -> None:
    """Print server connection and security details before Uvicorn starts."""
    output = console or Console()
    meta = Text()
    meta.append("sandwalk", style="bold white")
    meta.append(f" v{__version__}", style="dim")
    meta.append("\nAgent server", style="bold #40C9A2")

    if uds is not None:
        meta.append("\nSocket  ", style="dim")
        meta.append(str(uds.expanduser().resolve()))
    else:
        url = f"http://{host}:{port}"
        meta.append("\nServer  ", style="dim")
        meta.append(url)
        if ui_available:
            meta.append("\nDashboard  ", style="dim")
            meta.append(url)
        meta.append("\nAPI docs  ", style="dim")
        meta.append(f"{url}/docs")

    access = "Public" if public else "Local only"
    auth = "API key required" if auth_enabled else "no API key"
    meta.append("\nAccess  ", style="dim")
    meta.append(f"{access} · {auth}")
    meta.append("\nPress Ctrl+C to stop", style="dim")

    header = Table.grid(padding=(0, 2))
    header.add_column(no_wrap=True)
    header.add_column()
    logo = Text(BANNER.strip("\n"), style="#8B8B8B")
    header.add_row(
        Padding(logo, (1, 0, 0, 0)),
        Padding(meta, (0, 0, 0, 1)),
    )
    output.print()
    output.print(header)
    output.print()
