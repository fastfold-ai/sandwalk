"""
Execution trace rendering for tool calls.

Renders real-time trace panels showing tool name, arguments, results,
and timing — used by both the SDK runner and legacy executor paths.
"""

import time
from rich.console import Console
from rich.live import Live
from rich.text import Text

from ui.markdown import print_markdown_with_mermaid
from ui.status import SPINNERS, apply_gradient


def format_args(args: dict | None, max_value_len: int = 50) -> str:
    """Format tool arguments as a compact key=value string.

    Omits internal keys (starting with ``_``) and truncates long values.
    """
    if not args:
        return ""
    parts = []
    for k, v in args.items():
        if k.startswith("_"):
            continue
        v_str = str(v)
        if len(v_str) > max_value_len:
            v_str = v_str[:max_value_len] + "..."
        if isinstance(v, str):
            parts.append(f'{k}="{v_str}"')
        else:
            parts.append(f"{k}={v_str}")
    return ", ".join(parts)


def truncate_output(text: str, max_chars: int = 200) -> str:
    """Truncate tool output text, appending length info if trimmed."""
    if not text:
        return ""
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + f"... [{len(text)} chars total]"


def format_duration(seconds: float) -> str:
    """Format an elapsed duration with a sensible unit.

    Sub-second durations show milliseconds (e.g. ``42ms``) so fast tool calls
    don't all collapse to ``0.0s``; longer ones show seconds or ``m s``.
    """
    seconds = max(0.0, float(seconds))
    if seconds < 1:
        return f"{int(round(seconds * 1000))}ms"
    if seconds < 60:
        return f"{seconds:.1f}s"
    return f"{int(seconds // 60)}m {int(seconds % 60)}s"


class TraceRenderer:
    """Renders tool call traces to a Rich Console.

    Accepts a ``Console`` at construction so tests can pass
    ``Console(file=StringIO())`` to capture output.
    """

    def __init__(self, console: Console | None = None, config=None):
        self.console = console or Console()
        self.config = config

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

    def render_todos(self, todos) -> None:
        """Render a deepagents ``write_todos`` update as a checklist.

        ``todos`` is a list of ``{"content": str, "status": str}`` dicts. Status
        is one of pending / in_progress / completed (others rendered as pending).
        """
        if not isinstance(todos, list) or not todos:
            return

        marks = {
            "completed": ("[x]", "green"),
            "in_progress": ("[~]", "yellow"),
            "pending": ("[ ]", "dim"),
        }
        header = Text()
        header.append("  \u25b8 ", style="bold cyan")
        header.append("todos", style="cyan")
        done = sum(1 for t in todos if isinstance(t, dict) and t.get("status") == "completed")
        header.append(f"  {done}/{len(todos)}", style="dim")
        self.console.print(header)

        for todo in todos:
            if not isinstance(todo, dict):
                continue
            content = str(todo.get("content", "")).strip()
            if not content:
                continue
            status = str(todo.get("status", "pending")).lower()
            mark, style = marks.get(status, marks["pending"])
            line = Text("    ")
            line.append(f"{mark} ", style=style)
            line.append(content, style=("dim" if status == "completed" else style))
            self.console.print(line)

    def render_reasoning(self, text: str) -> None:
        """Render Claude's reasoning text between tool calls."""
        if not text or not text.strip():
            return
        
        try:
            print_markdown_with_mermaid(
                self.console,
                text,
                config=self.config,
            )
        except Exception:
            self.console.print(text)

    def render_task_started(self, task_id: str, description: str, task_type: str | None = None) -> None:
        """Render a background task start event."""
        line = Text()
        line.append("  ⌛ ", style="bold yellow")
        line.append("background task started", style="yellow")
        if task_type:
            line.append(f" [{task_type}]", style="dim")
        line.append(f"  {task_id}", style="dim")
        self.console.print(line)
        if description:
            self.console.print(f"    [dim]{description}[/dim]")

    def render_task_progress(
        self,
        task_id: str,
        description: str,
        usage: dict | None = None,
        last_tool_name: str | None = None,
    ) -> None:
        """Render a background task progress event."""
        line = Text()
        line.append("  … ", style="cyan")
        line.append("background task", style="cyan")
        line.append(f"  {task_id}", style="dim")
        self.console.print(line)

        details = []
        if description:
            details.append(description)
        if last_tool_name:
            details.append(f"last tool: {last_tool_name}")
        if usage and isinstance(usage, dict):
            total_tokens = usage.get("total_tokens")
            tool_uses = usage.get("tool_uses")
            usage_parts = []
            if total_tokens is not None:
                usage_parts.append(f"{total_tokens} tokens")
            if tool_uses is not None:
                usage_parts.append(f"{tool_uses} tool calls")
            if usage_parts:
                details.append(", ".join(usage_parts))
        if details:
            self.console.print(f"    [dim]{' · '.join(details)}[/dim]")

    def render_task_notification(
        self,
        task_id: str,
        status: str,
        summary: str = "",
        output_file: str = "",
    ) -> None:
        """Render a background task terminal notification."""
        status_lower = str(status or "").lower()
        if status_lower == "completed":
            icon = "✓"
            style = "green"
        elif status_lower == "failed":
            icon = "✗"
            style = "red"
        else:
            icon = "■"
            style = "yellow"

        header = Text()
        header.append(f"  {icon} ", style=f"bold {style}")
        header.append("background task", style=style)
        header.append(f"  {task_id}", style="dim")
        header.append(f"  {status_lower or 'unknown'}", style=f"bold {style}")
        self.console.print(header)
        if summary:
            self.console.print(f"    [dim]{summary}[/dim]")
        if output_file:
            self.console.print(f"    [dim]output: {output_file}[/dim]")
