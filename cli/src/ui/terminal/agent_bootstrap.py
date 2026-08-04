"""Mixin: bootstrap AgentLoop for InteractiveTerminal.run."""

from __future__ import annotations


class _AgentBootstrapMixin:
    def _bootstrap_agent_loop(self, resume_id: str | None = None) -> None:
        """Create/resume AgentLoop for the interactive session."""
        from agent.loop import AgentLoop

        if resume_id:
            try:
                if resume_id == "last":
                    self.agent = AgentLoop.resume_latest(self.session)
                else:
                    self.agent = AgentLoop.resume(self.session, resume_id)
                self._restore_usage_from_trajectory()
                n = len(self.agent.trajectory.turns)
                title = self.agent.trajectory.title or "untitled"
                self.console.print(
                    f"  [green]Resumed session[/green] "
                    f"[bold]{self.agent.trajectory.session_id}[/bold] — {title} ({n} turns)"
                )
                self._render_resumed_history(
                    self.console.width, turns=self.agent.trajectory.turns
                )
                self.console.print()
            except FileNotFoundError as e:
                self.console.print(f"  [yellow]{e}[/yellow]")
                self.console.print("  [dim]Use /sessions to list available session IDs.[/dim]")
                self.agent = AgentLoop(self.session)
        else:
            self.agent = AgentLoop(self.session)
