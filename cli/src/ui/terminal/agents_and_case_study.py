"""Mixin: _handle_agents_command, _run_orchestrated, _handle_case_study_command."""

from __future__ import annotations

class _AgentsAndCaseStudyMixin:
    def _handle_agents_command(self, query: str, context: dict):
        """Handle /agents N [query] command."""
        parts = query.split(maxsplit=2)
        # /agents N query  or  /agents N
        if len(parts) < 2 or not parts[1].isdigit():
            self.console.print(
                "  [dim]Usage: /agents N [query]  "
                "(e.g., /agents 3 profile lenalidomide)[/dim]"
            )
            return

        n_threads = int(parts[1])
        if n_threads < 1:
            self.console.print("  [dim]Need at least 1 agent.[/dim]")
            return

        if len(parts) > 2:
            agent_query = parts[2]
        else:
            # Prompt for query
            try:
                agent_query = self._prompt_session.prompt(
                    [("class:prompt", "  Research question: ")],
                ).strip()
            except (EOFError, KeyboardInterrupt):
                self.console.print("  [dim]Cancelled.[/dim]")
                return
            if not agent_query:
                self.console.print("  [dim]Cancelled.[/dim]")
                return

        self._run_orchestrated(agent_query, context, n_threads)

    def _run_orchestrated(self, query: str, context: dict, n_threads: int):
        """Run a query using the multi-agent orchestrator."""
        from agent.orchestrator import ResearchOrchestrator

        orchestrator = ResearchOrchestrator(
            self.session,
            n_threads=n_threads,
            trajectory=self.agent.trajectory if hasattr(self, 'agent') else None,
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
