"""Reasoning text and todo-checklist trace rendering mixin."""

from __future__ import annotations

from rich.text import Text


class _ReasoningMixin:
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

        from ui.traces import print_markdown_with_mermaid

        try:
            print_markdown_with_mermaid(
                self.console,
                text,
                config=self.config,
            )
        except Exception:
            self.console.print(text)
