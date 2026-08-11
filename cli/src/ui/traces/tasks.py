"""Background-task start/progress/notification trace rendering mixin."""

from __future__ import annotations

from rich.text import Text


class _TaskEventsMixin:
    def _task_sink_text(self, text: str) -> bool:
        sink = getattr(self, "sink", None)
        if sink is None:
            return False
        sink.write_text(text, kind="system")
        return True

    def render_task_started(self, task_id: str, description: str, task_type: str | None = None) -> None:
        """Render a background task start event."""
        line = f"  ⌛ background task started"
        if task_type:
            line += f" [{task_type}]"
        line += f"  {task_id}"
        if description:
            line += f"\n    {description}"
        if self._task_sink_text(line):
            return
        out = Text()
        out.append("  ⌛ ", style="bold yellow")
        out.append("background task started", style="yellow")
        if task_type:
            out.append(f" [{task_type}]", style="dim")
        out.append(f"  {task_id}", style="dim")
        self.console.print(out)
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
        text = f"  … background task  {task_id}"
        if details:
            text += f"\n    {' · '.join(details)}"
        if self._task_sink_text(text):
            return
        line = Text()
        line.append("  … ", style="cyan")
        line.append("background task", style="cyan")
        line.append(f"  {task_id}", style="dim")
        self.console.print(line)
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

        text = f"  {icon} background task  {task_id}  {status_lower or 'unknown'}"
        if summary:
            text += f"\n    {summary}"
        if output_file:
            text += f"\n    output: {output_file}"
        if self._task_sink_text(text):
            return

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
