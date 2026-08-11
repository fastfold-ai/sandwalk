"""Live progress rendering for parallel thread execution (rich Panel/Text)."""

import time

from rich.panel import Panel
from rich.text import Text

_SPINNER_FRAMES = ["-", "\\", "|", "/"]


def make_progress_callback(state_lock, statuses, step_counts, details):
    """Build a thread-local progress callback for AgentLoop.run."""
    def _for_thread(thread_id: int):
        def _cb(event: str, **payload):
            with state_lock:
                if statuses.get(thread_id) in {"completed", "failed"}:
                    return

                if event == "planning_start":
                    details[thread_id] = "planning"
                    return
                if event == "planned":
                    details[thread_id] = f"planned {payload.get('step_count', 0)} step(s)"
                    return
                if event == "execution_start":
                    details[thread_id] = f"executing (iteration {payload.get('iteration', 1)})"
                    return
                if event == "step_running":
                    details[thread_id] = (
                        f"step {payload.get('step_id', '?')} running: "
                        f"{payload.get('tool', '')}"
                    )
                    return
                if event == "step_completed":
                    completed = int(payload.get("completed_steps", step_counts[thread_id][0]))
                    failed = int(payload.get("failed_steps", step_counts[thread_id][1]))
                    step_counts[thread_id] = (completed, failed)
                    details[thread_id] = (
                        f"step {payload.get('step_id', '?')} completed: "
                        f"{payload.get('tool', '')}"
                    )
                    return
                if event == "step_failed":
                    completed = int(payload.get("completed_steps", step_counts[thread_id][0]))
                    failed = int(payload.get("failed_steps", step_counts[thread_id][1]))
                    step_counts[thread_id] = (completed, failed)
                    err = payload.get("error")
                    details[thread_id] = (
                        f"step {payload.get('step_id', '?')} failed: {payload.get('tool', '')}"
                        + (f" ({err})" if err else "")
                    )
                    return
                if event == "replan":
                    details[thread_id] = "replanning after observer feedback"
                    return
                if event == "replanned":
                    details[thread_id] = f"replanned {payload.get('step_count', 0)} step(s)"
                    return
                if event == "synthesis_start":
                    details[thread_id] = "synthesizing thread findings"
                    return
                if event == "synthesis_interrupted":
                    details[thread_id] = "synthesis interrupted"
                    return
                if event == "synthesis_end":
                    details[thread_id] = "thread synthesis complete"
                    return
        return _cb
    return _for_thread


def render_progress_panel(
    goals, evidence_board, state_lock, statuses, step_counts, details, start_times, durations,
) -> Panel:
    """Render the multi-thread progress panel."""
    lines = Text()
    lines.append("Multi-Agent Research\n\n")
    now = time.time()
    with state_lock:
        status_snapshot = dict(statuses)
        count_snapshot = dict(step_counts)
        detail_snapshot = dict(details)
        start_snapshot = dict(start_times)
        duration_snapshot = dict(durations)

    spinner = _SPINNER_FRAMES[int(now * 8) % len(_SPINNER_FRAMES)]
    running_threads = 0
    for g in goals:
        status = status_snapshot[g.thread_id]
        completed, failed = count_snapshot[g.thread_id]
        detail = detail_snapshot[g.thread_id]
        if status == "running":
            running_threads += 1
            elapsed = max(0.0, now - start_snapshot.get(g.thread_id, now))
            lines.append("  [", style="")
            lines.append(spinner, style="bold cyan")
            lines.append("] ", style="")
            lines.append(
                (
                    f"Thread {g.thread_id}: {g.angle} "
                    f"({completed} completed, {failed} failed) "
                    f"- {detail} [{elapsed:.1f}s]"
                ),
                style="cyan",
            )
        elif status == "completed":
            lines.append("  [", style="")
            lines.append("+", style="bold green")
            lines.append("] ", style="")
            elapsed = duration_snapshot.get(g.thread_id, 0.0)
            lines.append(
                (
                    f"Thread {g.thread_id}: {g.angle} "
                    f"({completed} completed, {failed} failed) "
                    f"- done [{elapsed:.1f}s]"
                ),
                style="green",
            )
        elif status == "failed":
            lines.append("  [", style="")
            lines.append("!", style="bold red")
            lines.append("] ", style="")
            elapsed = duration_snapshot.get(g.thread_id, 0.0)
            lines.append(
                f"Thread {g.thread_id}: {g.angle} ({detail}) [{elapsed:.1f}s]",
                style="red",
            )
        else:
            lines.append("  [ ] ", style="dim")
            lines.append(
                f"Thread {g.thread_id}: {g.angle} - {detail}",
                style="dim",
            )
        lines.append("\n")

    eb_count = len(evidence_board)
    lines.append(
        f"\n  Active threads: {running_threads}/{len(goals)}",
        style="dim",
    )
    if eb_count:
        lines.append(f"  |  Evidence board: {eb_count} entries", style="dim")

    return Panel(lines, title="Parallel Research", border_style="cyan")
