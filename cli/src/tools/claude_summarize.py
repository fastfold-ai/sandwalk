"""Claude reasoning tool: summarize and synthesize research findings."""

from tools import registry
from tools.claude_prompts import SUMMARIZE_SYSTEM_PROMPT, _build_context_section


@registry.register(
    name="claude.summarize",
    description="Synthesize and summarize research findings into actionable insights",
    category="claude",
    parameters={
        "goal": "What to summarize and the intended audience/purpose",
        "content": "Text content to summarize (optional if prior results available)",
    },
    usage_guide=(
        "Use after multiple analysis steps to distill key findings. Good for: "
        "executive summaries, decision briefs, literature synthesis. Typically "
        "used as a final step after data-gathering tools have run."
    ),
)
def summarize(goal: str, content: str = "", _session=None, _prior_results=None, **kwargs) -> dict:
    """Summarize and synthesize research findings."""
    if _session is None:
        return {
            "summary": "Summarization unavailable: no active session.",
            "error": "No session provided.",
        }

    llm = _session.get_llm()
    context_section = _build_context_section(_prior_results)

    user_msg = f"Summarize: {goal}"
    if content:
        user_msg += f"\n\nContent to summarize:\n{content}"

    system = SUMMARIZE_SYSTEM_PROMPT.format(context_section=context_section)

    from ui.status import ThinkingStatus

    try:
        with ThinkingStatus(_session.console, "summarizing"):
            response = llm.chat(
                system=system,
                messages=[{"role": "user", "content": user_msg}],
                temperature=0.2,
                max_tokens=1500,
            )
    except Exception as e:
        return {
            "summary": f"LLM summarization failed: {e}",
            "error": str(e),
        }

    return {
        "summary": response.content,
        "model": getattr(response, "model", "unknown"),
        "usage": getattr(response, "usage", None),
    }
