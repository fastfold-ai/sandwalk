"""TraceRenderer sink that writes into TranscriptStore instead of Rich."""

from __future__ import annotations

from typing import Any

from ui.terminal.transcript.store import TranscriptStore


class TranscriptSink:
    """Adapter used by ``TraceRenderer`` when an owned transcript is active."""

    def __init__(self, store: TranscriptStore) -> None:
        self.store = store

    def write_tool(
        self,
        *,
        name: str,
        args: dict | None = None,
        result: str = "",
        duration: float = 0.0,
        is_error: bool = False,
        expanded: bool = False,
    ) -> None:
        self.store.append_tool(
            name=name,
            args=args,
            result=result,
            duration=duration,
            is_error=is_error,
            expanded=expanded,
        )

    def write_text(self, text: str, *, kind: str = "text") -> None:
        if not text:
            return
        self.store.append_text(text, kind=kind)

    def write_separator(self) -> None:
        self.store.append_separator()


def rich_print_to_text(*args: Any, width: int = 100, **kwargs: Any) -> str:
    """Render Rich console.print args to a plain string for the transcript."""
    from io import StringIO

    from rich.console import Console

    buf = StringIO()
    console = Console(
        file=buf,
        width=max(40, width),
        force_terminal=False,
        color_system=None,
        highlight=False,
    )
    console.print(*args, **kwargs)
    return buf.getvalue().rstrip("\n")
