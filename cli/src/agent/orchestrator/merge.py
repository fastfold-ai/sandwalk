"""Merge per-thread plans into a single globally-renumbered plan."""

from agent.orchestrator.models import Plan, Step, ThreadResult


class MergeMixin:
    """Owns cross-thread step renumbering and provenance annotation."""

    def _merge_results(self, query: str,
                       thread_results: list[ThreadResult]) -> tuple[Plan, dict]:
        """Merge thread results with global step renumbering.

        Thread 1 steps 1-3 become global 1-3,
        Thread 2 steps 1-4 become global 4-7, etc.
        Step descriptions are prefixed with [Thread N: Angle] for provenance.
        """
        merged_steps: list[Step] = []
        merged_raw: dict = {}
        global_id = 1

        for tr in thread_results:
            if tr.error or tr.plan is None:
                continue

            # Find the angle from the goal
            angle = tr.goal[:40]

            for step in tr.plan.steps:
                # Create a new step with global ID and thread annotation
                new_step = Step(
                    id=global_id,
                    description=f"[Thread {tr.thread_id}: {angle}] {step.description}",
                    tool=step.tool,
                    tool_args=step.tool_args,
                    depends_on=[],  # No cross-thread deps
                    status=step.status,
                    result=step.result,
                )
                merged_steps.append(new_step)

                # Map results to new global IDs
                if step.id in tr.raw_results:
                    merged_raw[global_id] = tr.raw_results[step.id]

                global_id += 1

        merged_plan = Plan(
            query=query,
            steps=merged_steps,
        )

        return merged_plan, merged_raw
