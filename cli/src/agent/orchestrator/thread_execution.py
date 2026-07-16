"""Parallel thread execution: worker pool, live progress, and per-thread sessions."""

import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from io import StringIO

from rich.console import Console

from agent.orchestrator.models import ThreadGoal, ThreadResult
from agent.orchestrator.progress_display import make_progress_callback, render_progress_panel
from agent.session import Session

logger = logging.getLogger("orchestrator")


class ThreadExecutionMixin:
    """Owns the ThreadPoolExecutor loop and single-thread worker sessions."""

    def _execute_threads(self, query: str, goals: list[ThreadGoal],
                         context: dict) -> list[ThreadResult]:
        """Execute all thread goals in parallel using ThreadPoolExecutor."""
        thread_results: list[ThreadResult] = []
        # Track per-thread status for live display.
        statuses: dict[int, str] = {g.thread_id: "pending" for g in goals}
        step_counts: dict[int, tuple[int, int]] = {g.thread_id: (0, 0) for g in goals}
        details: dict[int, str] = {g.thread_id: "queued" for g in goals}
        start_times: dict[int, float] = {}
        durations: dict[int, float] = {}
        state_lock = threading.Lock()

        progress_callback_for = make_progress_callback(state_lock, statuses, step_counts, details)

        def update_display():
            return render_progress_panel(
                goals, self.evidence_board, state_lock,
                statuses, step_counts, details, start_times, durations,
            )

        with self._live_display(update_display()) as live:
            with ThreadPoolExecutor(max_workers=self.n_threads) as pool:
                futures = {}
                for goal in goals:
                    with state_lock:
                        statuses[goal.thread_id] = "running"
                        details[goal.thread_id] = "starting worker"
                        start_times[goal.thread_id] = time.time()
                    future = pool.submit(
                        self._execute_single_thread,
                        query,
                        goal,
                        context,
                        progress_callback_for(goal.thread_id),
                    )
                    futures[future] = goal

                for future in as_completed(futures):
                    goal = futures[future]
                    try:
                        result = future.result()
                        thread_results.append(result)
                        with state_lock:
                            step_counts[goal.thread_id] = (
                                result.completed_steps, result.failed_steps
                            )
                            statuses[goal.thread_id] = (
                                "completed" if not result.error else "failed"
                            )
                            durations[goal.thread_id] = result.duration_s
                            if result.error:
                                details[goal.thread_id] = f"error: {result.error}"
                            else:
                                details[goal.thread_id] = "thread complete"
                    except Exception as e:
                        logger.error(
                            "Thread %d (%s) raised exception: %s",
                            goal.thread_id, goal.angle, e,
                        )
                        thread_results.append(ThreadResult(
                            thread_id=goal.thread_id,
                            goal=goal.goal,
                            error=str(e),
                        ))
                        with state_lock:
                            statuses[goal.thread_id] = "failed"
                            details[goal.thread_id] = f"error: {e}"
                            durations[goal.thread_id] = max(
                                0.0, time.time() - start_times.get(goal.thread_id, time.time())
                            )

                    live.update(update_display())

        # Sort by thread_id for consistent ordering
        thread_results.sort(key=lambda r: r.thread_id)
        return thread_results

    def _execute_single_thread(self, query: str, goal: ThreadGoal,
                               context: dict, progress_callback=None) -> ThreadResult:
        """Execute a single research thread (runs in a worker thread).

        Creates its own Session and AgentLoop for thread safety.
        """
        from agent.config import Config
        from agent.loop import AgentLoop

        t0 = time.time()

        # Each thread gets its own session with a silent console
        worker_console = Console(file=StringIO(), quiet=True)
        worker_config = Config.load()  # Fresh config copy
        worker_session = Session(config=worker_config, verbose=False)
        worker_session.console = worker_console

        # Create AgentLoop with evidence board and headless mode
        agent = AgentLoop(
            worker_session,
            evidence_board=self.evidence_board,
            thread_id=goal.thread_id,
            headless=True,
        )

        # Build thread-specific context
        thread_context = dict(context)
        thread_context["research_angle"] = goal.angle
        if goal.suggested_tools:
            thread_context["suggested_tools"] = ", ".join(goal.suggested_tools)

        try:
            result = agent.run(
                goal.goal,
                thread_context,
                progress_callback=progress_callback,
            )

            completed = [s for s in result.plan.steps if s.status == "completed"]
            failed = [s for s in result.plan.steps if s.status == "failed"]

            return ThreadResult(
                thread_id=goal.thread_id,
                goal=goal.goal,
                plan=result.plan,
                raw_results=result.raw_results,
                completed_steps=len(completed),
                failed_steps=len(failed),
                duration_s=time.time() - t0,
            )
        except Exception as e:
            logger.error("Thread %d failed: %s", goal.thread_id, e)
            if callable(progress_callback):
                try:
                    progress_callback("thread_error", error=str(e))
                except Exception:
                    pass
            return ThreadResult(
                thread_id=goal.thread_id,
                goal=goal.goal,
                duration_s=time.time() - t0,
                error=str(e),
            )
