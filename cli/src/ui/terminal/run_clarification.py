"""Mixin: _run_with_clarification, _print_exit_with_resume_hint."""

from __future__ import annotations

import re
from ui.terminal.mentions import build_mention_context
from ui.terminal.mentions import extract_mentions


class _RunClarificationMixin:
    def _run_with_clarification(
        self,
        query: str,
        context: dict,
        progress_callback=None,
    ):
        """Run a query, handling clarification requests interactively."""
        from agent.loop import ClarificationNeeded

        if not self._ensure_llm_ready_for_query():
            return None

        run_context = dict(context)

        # Apply (or clear) active CLI specialist each run so /specialist use|clear
        # takes effect without restarting the session.
        try:
            from agent.specialists_manage import (
                apply_specialist_to_context,
                get_active_specialist,
            )

            run_context.pop("specialist_instructions", None)
            run_context.pop("allowed_skill_names", None)
            # Drop prior specialist MCP filter; re-apply only when active.
            if "mcp_servers" in run_context and get_active_specialist() is None:
                run_context.pop("mcp_servers", None)
            active = get_active_specialist()
            if active is not None:
                run_context = apply_specialist_to_context(run_context, active)
        except Exception:  # noqa: BLE001
            pass

        # Prefer the CLI-selected sandbox backend for this run.
        try:
            from agent.sandbox_manage import get_sandbox_backend

            run_context["sandbox_backend"] = get_sandbox_backend()
            self._refresh_cli_sandbox_label()
        except Exception:  # noqa: BLE001
            run_context.setdefault("sandbox_backend", "builtin")

        # Extract @mentions and inject into context
        cleaned_query, mention_tools, mention_datasets, mention_workflows = extract_mentions(query)
        if mention_tools or mention_datasets or mention_workflows:
            mention_ctx = build_mention_context(mention_tools, mention_datasets, mention_workflows)
            run_context["mention_context"] = mention_ctx
            query = cleaned_query

        max_clarifications = 3  # Prevent infinite clarification loops

        for _ in range(max_clarifications):
            try:
                return self.agent.run(
                    query,
                    run_context,
                    progress_callback=progress_callback,
                )
            except ClarificationNeeded as e:
                clar = e.clarification
                self.console.print(f"  [cyan]{clar.question}[/cyan]")
                if clar.suggestions:
                    self.console.print(f"  [dim]e.g. {', '.join(clar.suggestions[:3])}[/dim]")

                try:
                    answer = self._prompt_session.prompt(
                        [("class:prompt", "  ❯ ")],
                    ).strip()
                except (EOFError, KeyboardInterrupt):
                    self.console.print("  [dim]Cancelled.[/dim]")
                    return None

                if not answer:
                    self.console.print("  [dim]Cancelled.[/dim]")
                    return None

                # Add the answer to context using the missing parameter name
                if clar.missing:
                    run_context[clar.missing[0]] = answer
                # Also append to the query so the planner gets full context
                query = f"{query} — {answer}"

        return self.agent.run(
            query,
            run_context,
            progress_callback=progress_callback,
        )

    def _print_exit_with_resume_hint(self) -> None:
        """Print exit message with a copyable resume command."""
        self.console.print("\nGoodbye!\n")
        session_id = None
        has_messages = False
        if hasattr(self, "agent") and getattr(self.agent, "trajectory", None):
            trajectory = self.agent.trajectory
            session_id = getattr(trajectory, "session_id", None)
            has_messages = bool(getattr(trajectory, "turns", None))
        if session_id and has_messages:
            self.console.print("Resume this session with:")
            self.console.print(f"[cyan]sandwalk --resume {session_id}[/cyan]")
