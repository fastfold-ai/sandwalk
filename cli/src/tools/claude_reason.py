"""Claude reasoning tools: open-ended expert reasoning and option comparison."""

from tools import registry
from tools.claude_prompts import (
    COMPARE_SYSTEM_PROMPT,
    REASON_SYSTEM_PROMPT,
    _build_context_section,
)


@registry.register(
    name="claude.reason",
    description="Expert reasoning about drug discovery questions using Claude",
    category="claude",
    parameters={
        "goal": "The question or reasoning task to address",
        "context": "Additional context (e.g., prior findings, constraints)",
    },
    usage_guide=(
        "Use when the query requires expert scientific reasoning, interpretation, "
        "or hypothesis generation that no pre-built tool covers. Good for: "
        "mechanism-of-action reasoning, experimental design advice, literature "
        "interpretation, risk assessment rationale, strategic recommendations. "
        "Do NOT use for tasks that a pre-built tool handles (data retrieval, "
        "similarity search, etc.) — those are faster and cheaper."
    ),
)
def reason(goal: str, context: str = "", _session=None, _prior_results=None, **kwargs) -> dict:
    """Use Claude for expert reasoning on drug discovery questions."""
    if _session is None:
        return {
            "summary": "Reasoning unavailable: no active session.",
            "error": "No session provided.",
        }

    llm = _session.get_llm()
    context_section = _build_context_section(_prior_results)

    user_msg = f"Question: {goal}"
    if context:
        user_msg += f"\n\nAdditional context: {context}"

    system = REASON_SYSTEM_PROMPT.format(context_section=context_section)

    from ui.status import ThinkingStatus

    try:
        with ThinkingStatus(_session.console, "reasoning"):
            response = llm.chat(
                system=system,
                messages=[{"role": "user", "content": user_msg}],
                temperature=0.3,
                max_tokens=2048,
            )
    except Exception as e:
        return {
            "summary": f"LLM reasoning failed: {e}",
            "error": str(e),
        }

    return {
        "summary": response.content,
        "model": getattr(response, "model", "unknown"),
        "usage": getattr(response, "usage", None),
    }


@registry.register(
    name="claude.compare",
    description="Compare and evaluate multiple options (compounds, targets, strategies)",
    category="claude",
    parameters={
        "goal": "What to compare and the decision to make",
        "options": "Comma-separated list of options to compare",
        "criteria": "Evaluation criteria (optional)",
    },
    usage_guide=(
        "Use when the user needs to choose between options — compounds, targets, "
        "indications, strategies, CROs, etc. Provides structured comparison with "
        "a recommendation. Combine with pre-built tools first to gather data, "
        "then use claude.compare to interpret and decide."
    ),
)
def compare(
    goal: str, options: str = "", criteria: str = "", _session=None, _prior_results=None, **kwargs
) -> dict:
    """Compare multiple options using Claude's reasoning."""
    if _session is None:
        return {
            "summary": "Comparison unavailable: no active session.",
            "error": "No session provided.",
        }

    llm = _session.get_llm()
    context_section = _build_context_section(_prior_results)

    user_msg = f"Decision: {goal}"
    if options:
        user_msg += f"\n\nOptions to compare: {options}"
    if criteria:
        user_msg += f"\n\nEvaluation criteria: {criteria}"

    system = COMPARE_SYSTEM_PROMPT.format(context_section=context_section)

    from ui.status import ThinkingStatus

    try:
        with ThinkingStatus(_session.console, "comparing"):
            response = llm.chat(
                system=system,
                messages=[{"role": "user", "content": user_msg}],
                temperature=0.2,
                max_tokens=2048,
            )
    except Exception as e:
        return {
            "summary": f"LLM comparison failed: {e}",
            "error": str(e),
        }

    return {
        "summary": response.content,
        "model": getattr(response, "model", "unknown"),
        "usage": getattr(response, "usage", None),
    }
