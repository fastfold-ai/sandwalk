"""Query decomposition into thread goals, and cross-thread synthesis."""

import json
import logging

from agent.orchestrator.models import ThreadGoal
from agent.orchestrator.prompts import META_PLANNER_SYSTEM_PROMPT

logger = logging.getLogger("orchestrator")


class PlanningMixin:
    """Owns LLM-driven query decomposition and final report synthesis."""

    def _synthesize(self, query: str, merged_plan, merged_raw: dict,
                    thread_results: list) -> str:
        """Merge thread findings into a single coherent report via LLM."""
        llm = self.session.get_llm()

        # Build a compact summary of what each thread found
        findings: list[str] = []
        for tr in thread_results:
            if tr.error or tr.plan is None:
                findings.append(
                    f"Thread {tr.thread_id} ({tr.goal[:60]}): FAILED — {tr.error}"
                )
                continue
            step_summaries = []
            for step in tr.plan.steps:
                if step.status == "completed" and step.result:
                    result = step.result
                    if isinstance(result, dict):
                        text = result.get("summary") or str(result)[:300]
                    else:
                        text = str(result)[:300]
                    step_summaries.append(f"  - [{step.tool}] {text}")
            findings.append(
                f"Thread {tr.thread_id} — {tr.goal[:80]} "
                f"({tr.completed_steps} steps):\n" + "\n".join(step_summaries)
            )

        findings_text = "\n\n".join(findings)
        user_msg = (
            f"Original query: {query}\n\n"
            f"Parallel research thread findings:\n\n{findings_text}\n\n"
            f"Synthesize all findings into a single comprehensive research report. "
            f"Integrate evidence across threads, highlight key conclusions, and note "
            f"any gaps or conflicts between thread findings."
        )

        with self._thinking_status("synthesizing"):
            response = llm.chat(
                system=(
                    "You are a senior drug discovery researcher. Synthesize parallel "
                    "research thread findings into a single coherent, evidence-backed "
                    "report. Be concise but thorough. Use markdown formatting."
                ),
                messages=[{"role": "user", "content": user_msg}],
                max_tokens=4096,
            )

        return (response.content or "").strip()

    def _decompose(self, query: str, context: dict) -> list[ThreadGoal]:
        """Use LLM to decompose query into N independent thread goals."""
        llm = self.session.get_llm()

        context_str = ""
        if context:
            parts = []
            for k, v in context.items():
                parts.append(f"{k}: {v}")
            context_str = "\n\nAdditional context:\n" + "\n".join(parts)

        user_msg = (
            f"Decompose this drug discovery query into exactly {self.n_threads} "
            f"independent, parallel research threads:\n\n"
            f"Query: {query}{context_str}\n\n"
            f"Return a JSON array with {self.n_threads} thread goals."
        )

        with self._thinking_status("decomposing"):
            response = llm.chat(
                system=META_PLANNER_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_msg}],
                temperature=0.3,
                max_tokens=2000,
            )

        text = (response.content or "").strip()

        # Parse JSON
        try:
            # Find JSON array in response
            start = text.index("[")
            end = text.rindex("]") + 1
            goals_data = json.loads(text[start:end])
        except (ValueError, json.JSONDecodeError):
            logger.warning("Meta-planner returned unparseable JSON, falling back to single thread")
            return [ThreadGoal(
                thread_id=1,
                angle="Full Research",
                goal=query,
            )]

        goals = []
        for i, g in enumerate(goals_data[:self.n_threads], start=1):
            goals.append(ThreadGoal(
                thread_id=i,
                angle=g.get("angle", f"Thread {i}"),
                goal=g.get("goal", query),
                suggested_tools=g.get("suggested_tools", []),
                context=g.get("context", ""),
            ))

        if not goals:
            goals = [ThreadGoal(thread_id=1, angle="Full Research", goal=query)]

        return goals
