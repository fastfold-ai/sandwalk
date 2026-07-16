"""Build the human-readable warning list for a budget estimate."""

from __future__ import annotations

from agent_server.models import Specialist


def build_warnings(
    *,
    provider: str,
    uncapped_total: int,
    tool_total: int,
    deepagents_count: int,
    total_tokens: int,
    specialist: Specialist | None,
) -> list[str]:
    warnings: list[str] = []
    if provider == "openai" and uncapped_total > 128:
        warnings.append(
            f"OpenAI tool ceiling is 128; {uncapped_total} tools before cap "
            f"(kept {tool_total} including {deepagents_count} deepagents builtins)."
        )
    if provider == "openai" and tool_total > 116:
        warnings.append(f"Estimated {tool_total} tools after OpenAI headroom budget.")
    if total_tokens > 100_000:
        warnings.append(
            "Estimated input exceeds 100k tokens — trim MCP servers, use a "
            "lighter specialist, or keep PTC mode."
        )
    if specialist is not None and not (specialist.tool_names or []):
        warnings.append(
            "This specialist has an empty tool allowlist — only runtime "
            "pins (run_python / search_tools / shell) remain."
        )
    warnings.append(
        "Estimate is tiktoken on assembled text/schemas. Provider-billed "
        "input_tokens can be ~5–15% higher due to tools JSON envelope overhead."
    )
    return warnings
