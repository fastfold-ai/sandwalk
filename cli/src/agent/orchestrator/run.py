"""Top-level run() entry point: decompose, execute, merge, synthesize, save."""

import time

from agent.orchestrator.models import OrchestratorResult, ThreadGoal


class RunMixin:
    """Owns the run() orchestration sequence."""

    def run(self, query: str, context: dict = None,
            preset_goals: list[ThreadGoal] = None) -> OrchestratorResult:
        """Execute a multi-agent parallel research query.

        1. Decompose query into N thread goals via meta-planner (or use preset_goals)
        2. Execute threads in parallel with shared evidence board
        3. Merge results with global step renumbering
        4. Synthesize merged report

        Parameters
        ----------
        query : str
            The research query.
        context : dict, optional
            Additional context for the query.
        preset_goals : list[ThreadGoal], optional
            Pre-defined research angles (skips LLM decomposition).
            Used by case studies and other curated workflows.
        """
        t0 = time.time()
        context = context or {}

        if preset_goals is not None:
            # Use pre-defined goals — skip LLM decomposition
            goals = preset_goals
            self.n_threads = len(goals)
            self.console.print(
                f"\n  [cyan]Multi-agent mode:[/cyan] using {len(goals)} "
                f"pre-defined research angles"
            )
        else:
            self.console.print(
                f"\n  [cyan]Multi-agent mode:[/cyan] decomposing into "
                f"{self.n_threads} parallel research threads..."
            )
            # 1. Decompose
            goals = self._decompose(query, context)

        self.console.print(
            "  [cyan]Threads planned:[/cyan] "
            + ", ".join(f"[bold]{g.angle}[/bold]" for g in goals)
        )
        self.console.print()

        # 2. Execute threads in parallel
        thread_results = self._execute_threads(query, goals, context)

        # 3. Merge results
        merged_plan, merged_raw = self._merge_results(query, thread_results)

        # 4. Meta-synthesize using the executor's synthesis
        self.console.print(
            f"\n  [cyan]Synthesizing[/cyan] merged results from "
            f"{len(thread_results)} threads..."
        )

        summary = self._synthesize(query, merged_plan, merged_raw, thread_results)

        duration = time.time() - t0

        # Compute stats
        total_steps = sum(tr.completed_steps + tr.failed_steps for tr in thread_results)
        completed_steps = sum(tr.completed_steps for tr in thread_results)
        failed_steps = sum(tr.failed_steps for tr in thread_results)

        result = OrchestratorResult(
            threads=thread_results,
            merged_plan=merged_plan,
            summary=summary,
            raw_results=merged_raw,
            duration_s=duration,
            n_threads=len(thread_results),
            total_steps=total_steps,
            completed_steps=completed_steps,
            failed_steps=failed_steps,
        )

        # Auto-save report
        self._auto_save_report(query, result)

        # Print stats
        self.console.print(
            f"\n  [dim]{len(thread_results)} threads | "
            f"{completed_steps}/{total_steps} steps | "
            f"{len(self.evidence_board)} evidence entries | "
            f"{duration:.1f}s[/dim]"
        )

        return result
