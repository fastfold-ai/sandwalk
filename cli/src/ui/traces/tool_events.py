"""Tool call start/complete/error trace rendering mixin."""

from __future__ import annotations

from rich.text import Text

from ui.traces.formatting import format_args, format_duration, truncate_output
from ui.traces.tool_expand import ToolCard, ToolExpandStore


def _tools_collapsed(config) -> bool:
    """True when tool traces should print as one-liners (default)."""
    if config is None:
        return True
    if not bool(config.get("agent.group_tool_traces", True)):
        return False
    try:
        return int(config.get("agent.tool_trace_detail_limit", 0) or 0) <= 0
    except (TypeError, ValueError):
        return True


class _ToolEventsMixin:
    expand_store: ToolExpandStore | None

    def tools_collapsed(self) -> bool:
        return _tools_collapsed(getattr(self, "config", None))

    def _sink(self):
        return getattr(self, "sink", None)

    def render_tool_start(self, name: str, args: dict | None = None) -> None:
        """Render a running tool indicator (suppressed when collapsed)."""
        if self.tools_collapsed():
            return
        clean = name.replace("mcp__ct-tools__", "")
        args_str = format_args(args)
        sink = self._sink()
        if sink is not None:
            line = f"  ▸ {clean}"
            if args_str:
                line += f"  {args_str}"
            sink.write_text(line, kind="system")
            return

        line = Text()
        line.append("  \u25b8 ", style="bold cyan")
        line.append(clean, style="cyan")
        if args_str:
            line.append(f"  {args_str}", style="dim")
        self.console.print(line)
        store = getattr(self, "expand_store", None)
        if store is not None:
            store.note_lines(1)

    def render_tool_compact(self, name: str, duration: float = 0.0,
                            *, args: dict | None = None, result: str = "",
                            is_error: bool = False) -> None:
        """One-line collapsed tool result (Claude Code–style)."""
        clean = name.replace("mcp__ct-tools__", "")
        sink = self._sink()
        if sink is not None:
            sink.write_tool(
                name=clean,
                args=args,
                result=result,
                duration=duration,
                is_error=is_error,
                expanded=False,
            )
            return

        line = Text()
        if is_error:
            line.append("  \u2717 ", style="bold red")
            line.append("Ran ", style="dim")
            line.append(clean, style="red")
        else:
            line.append("  \u2713 ", style="bold green")
            line.append("Ran ", style="dim")
            line.append(clean, style="green")
        if duration > 0:
            line.append(f"  {format_duration(duration)}", style="dim")
        line.append(" \u25b8", style="dim")
        self.console.print(line)
        store = getattr(self, "expand_store", None)
        if store is not None:
            store.add(
                name=clean,
                args=args,
                result=result,
                duration=duration,
                is_error=is_error,
                lines=1,
            )

    def render_tool_complete(
        self,
        name: str,
        args: dict | None = None,
        result: str = "",
        duration: float = 0.0,
    ) -> None:
        """Render a completed tool trace — collapsed one-liner by default."""
        if self.tools_collapsed():
            self.render_tool_compact(
                name, duration, args=args, result=result, is_error=False,
            )
            return
        clean = name.replace("mcp__ct-tools__", "")
        sink = self._sink()
        if sink is not None:
            # Verbose mode: store already-expanded card.
            sink.write_tool(
                name=clean,
                args=args,
                result=result,
                duration=duration,
                is_error=False,
                expanded=True,
            )
            return

        args_str = format_args(args)
        summary = truncate_output(result)

        header = Text()
        header.append("  \u2713 ", style="bold green")
        header.append(clean, style="green")
        if duration > 0:
            header.append(f"  {format_duration(duration)}", style="dim")
        self.console.print(header)

        printed = 1
        if args_str:
            self.console.print(f"    [dim]{args_str}[/dim]")
            printed += 1
        if summary:
            self.console.print(f"    [dim]{summary}[/dim]")
            printed += summary.count("\n") + 1
        store = getattr(self, "expand_store", None)
        if store is not None:
            store.note_lines(printed)

    def render_tool_error(self, name: str, error: str = "") -> None:
        """Render a failed tool — compact header when collapsed."""
        if self.tools_collapsed():
            self.render_tool_compact(
                name, 0.0, args=None, result=error, is_error=True,
            )
            if error and self._sink() is None:
                err_text = truncate_output(error)
                self.console.print(f"    [red]{err_text}[/red]")
                store = getattr(self, "expand_store", None)
                if store is not None:
                    store.note_lines(err_text.count("\n") + 1)
            return
        clean = name.replace("mcp__ct-tools__", "")
        sink = self._sink()
        if sink is not None:
            sink.write_tool(
                name=clean,
                args=None,
                result=error,
                duration=0.0,
                is_error=True,
                expanded=True,
            )
            return
        header = Text()
        header.append("  \u2717 ", style="bold red")
        header.append(clean, style="red")
        header.append(" \u25b8", style="dim")
        self.console.print(header)
        printed = 1
        if error:
            err_text = truncate_output(error)
            self.console.print(f"    [red]{err_text}[/red]")
            printed += err_text.count("\n") + 1
        store = getattr(self, "expand_store", None)
        if store is not None:
            store.note_lines(printed)

    def render_tool_expanded(self, card: ToolCard) -> None:
        """Legacy Rich dump for a previously collapsed card (non-transcript)."""
        clean = card.name.replace("mcp__ct-tools__", "")
        args_str = format_args(card.args)
        if card.is_error:
            header = Text()
            header.append("  \u2717 ", style="bold red")
            header.append(clean, style="red")
            if card.duration > 0:
                header.append(f"  {format_duration(card.duration)}", style="dim")
            self.console.print(header)
            if card.result:
                self.console.print(f"    [red]{truncate_output(card.result)}[/red]")
            return
        header = Text()
        header.append("  \u2713 ", style="bold green")
        header.append(clean, style="green")
        if card.duration > 0:
            header.append(f"  {format_duration(card.duration)}", style="dim")
        self.console.print(header)
        if args_str:
            self.console.print(f"    [dim]{args_str}[/dim]")
        summary = truncate_output(card.result)
        if summary:
            self.console.print(f"    [dim]{summary}[/dim]")
