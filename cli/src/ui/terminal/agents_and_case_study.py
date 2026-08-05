"""Mixin: _handle_agents_command, _run_orchestrated, _handle_case_study_command."""

from __future__ import annotations

import threading
import time


class _AgentsAndCaseStudyMixin:
    def _handle_agents_command(self, query: str, context: dict):
        """Handle /agents N <query> without suspending the fullscreen TUI.

        Nested PromptSession / ``run_in_terminal`` blanks the alt screen
        (blink). Require the research question on the command line and run the
        orchestrator on a worker thread so the UI stays responsive.
        """
        parts = query.split(maxsplit=2)
        # /agents N query
        if len(parts) < 2 or not parts[1].isdigit():
            self.console.print(
                "  [dim]Usage: /agents N <query>  "
                "(e.g., /agents 3 profile lenalidomide)[/dim]"
            )
            return

        n_threads = int(parts[1])
        if n_threads < 1:
            self.console.print("  [dim]Need at least 1 agent.[/dim]")
            return

        if len(parts) < 3 or not parts[2].strip():
            self.console.print(
                "  [dim]Usage: /agents N <query>  "
                "(e.g., /agents 3 profile lenalidomide)[/dim]"
            )
            return

        self._start_orchestrated(parts[2].strip(), context, n_threads)

    def _start_orchestrated(self, query: str, context: dict, n_threads: int) -> None:
        """Run multi-agent orchestration on the query worker thread."""
        if self._has_active_query():
            self.console.print(
                "  [dim]Command unavailable while a generation is running.[/dim]"
            )
            return

        start_refresh = False
        with self._run_lock:
            worker = self._worker_thread
            if worker and worker.is_alive():
                self.console.print(
                    "  [dim]Command unavailable while a generation is running.[/dim]"
                )
                return

            def _worker() -> None:
                try:
                    with self._run_lock:
                        self._active_query = query
                        self._active_query_started_at = time.time()
                        self._active_activity = f"Running {n_threads} agents…"
                        self._active_activity_updated_at = time.time()
                        self._active_input_tokens = 0
                        self._active_output_tokens = 0
                        self._active_streamed_chars = 0
                    self._run_orchestrated(query, context, n_threads)
                finally:
                    with self._run_lock:
                        self._worker_thread = None
                    if hasattr(self, "_clear_toolbar_busy"):
                        self._clear_toolbar_busy()
                    else:
                        with self._run_lock:
                            self._active_query = None

            worker = threading.Thread(
                target=_worker,
                daemon=True,
                name="sandwalk-agents",
            )
            self._worker_thread = worker
            self._active_query = query
            self._active_query_started_at = time.time()
            self._active_activity = f"Running {n_threads} agents…"
            self._active_activity_updated_at = time.time()
            self._active_input_tokens = 0
            self._active_output_tokens = 0
            self._active_streamed_chars = 0
            start_refresh = True
            worker.start()

        if start_refresh and hasattr(self, "_ensure_live_refresh_thread"):
            self._ensure_live_refresh_thread()

    def _run_orchestrated(self, query: str, context: dict, n_threads: int):
        """Run a query using the multi-agent orchestrator (blocking)."""
        from agent.orchestrator import ResearchOrchestrator

        orchestrator = ResearchOrchestrator(
            self.session,
            n_threads=n_threads,
            trajectory=self.agent.trajectory if hasattr(self, "agent") else None,
        )

        try:
            self.console.print()
            result = orchestrator.run(query, context)
            self.console.print()

            if result is not None:
                self._last_response = result.summary
                self._update_suggestions(query, result.merged_plan, result)
        except KeyboardInterrupt:
            self.console.print("\n  [yellow]Interrupted.[/yellow]")
        except Exception as e:
            self.console.print(f"\n  [red]Orchestrator error:[/red] {e}")

    def _handle_case_study_command(self, query: str, context: dict):
        """Handle /case-study <id> or /case-study list."""
        from agent.case_studies import CASE_STUDIES, run_case_study

        parts = query.split(maxsplit=1)
        arg = parts[1].strip() if len(parts) > 1 else ""

        if not arg or arg == "list":
            from rich.table import Table

            table = Table(title="Case Studies")
            table.add_column("ID", style="cyan")
            table.add_column("Drug")
            table.add_column("Threads", style="dim")
            table.add_column("Description")
            for case_id, case in CASE_STUDIES.items():
                table.add_row(
                    case_id,
                    case.name,
                    str(len(case.thread_goals)),
                    case.description[:80] + ("..." if len(case.description) > 80 else ""),
                )
            self.console.print(table)
            self.console.print(
                "\n  [dim]Usage: /case-study <id>  (e.g., /case-study revlimid)[/dim]"
            )
            return

        case_id = arg.split()[0].lower()
        if case_id not in CASE_STUDIES:
            available = ", ".join(sorted(CASE_STUDIES.keys()))
            self.console.print(
                f"  [red]Unknown case study '{case_id}'.[/red] Available: {available}"
            )
            return

        case = CASE_STUDIES[case_id]
        self.console.print(
            f"\n  [cyan]Case Study:[/cyan] [bold]{case.name}[/bold]"
            f"\n  [dim]{case.description}[/dim]\n"
        )

        try:
            result = run_case_study(self.session, case_id)
            self.console.print()

            if result is not None:
                self._last_response = result.summary
                self._update_suggestions(case.compound, result.merged_plan, result)
        except KeyboardInterrupt:
            self.console.print("\n  [yellow]Interrupted.[/yellow]")
        except Exception as e:
            self.console.print(f"\n  [red]Case study error:[/red] {e}")
