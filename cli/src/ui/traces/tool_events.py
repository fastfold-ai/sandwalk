"""Tool call start/complete/error trace rendering mixin."""

from __future__ import annotations

from rich.text import Text

from ui.traces.formatting import format_args, format_duration, truncate_output


class _ToolEventsMixin:
    def render_tool_start(self, name: str, args: dict | None = None) -> None:
        """Render a running tool indicator."""
        clean = name.replace("mcp__ct-tools__", "")
        args_str = format_args(args)

        line = Text()
        line.append("  \u25b8 ", style="bold cyan")
        line.append(clean, style="cyan")
        if args_str:
            line.append(f"  {args_str}", style="dim")
        self.console.print(line)

    def render_tool_complete(
        self,
        name: str,
        args: dict | None = None,
        result: str = "",
        duration: float = 0.0,
    ) -> None:
        """Render a completed tool trace with result summary and timing."""
        clean = name.replace("mcp__ct-tools__", "")
        args_str = format_args(args)
        summary = truncate_output(result)

        header = Text()
        header.append("  \u2713 ", style="bold green")
        header.append(clean, style="green")
        if duration > 0:
            header.append(f"  {format_duration(duration)}", style="dim")
        self.console.print(header)

        if args_str:
            self.console.print(f"    [dim]{args_str}[/dim]")
        if summary:
            self.console.print(f"    [dim]{summary}[/dim]")

    def render_tool_error(self, name: str, error: str = "") -> None:
        """Render a failed tool trace with error message."""
        clean = name.replace("mcp__ct-tools__", "")
        header = Text()
        header.append("  \u2717 ", style="bold red")
        header.append(clean, style="red")
        self.console.print(header)
        if error:
            err_text = truncate_output(error)
            self.console.print(f"    [red]{err_text}[/red]")
