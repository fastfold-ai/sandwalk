"""Background-task start/progress/notification trace rendering mixin."""

from __future__ import annotations

from rich.text import Text


class _TaskEventsMixin:
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
