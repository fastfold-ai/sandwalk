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
    billed_matched: bool = False,
    token_count_method: str = "tiktoken",
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
    supported = {"anthropic", "openai", "google"}
    if billed_matched:
        label = {
            "anthropic": "Anthropic count_tokens",
            "openai": "OpenAI input_tokens",
            "google": "Gemini count_tokens",
        }.get(provider, f"{provider} count_tokens")
        warnings.append(
            f"Total uses {label} on the assembled first-turn request "
            "(same tokenizer family as chat Input for this provider)."
        )
    elif token_count_method == "provider" and provider not in supported:
        warnings.append(
            f"Provider counting is not available for {provider or 'this provider'}; "
            "fell back to tiktoken. Supported: Anthropic, OpenAI, Google."
        )
    elif token_count_method == "provider":
        warnings.append(
            "Provider counting failed (missing/invalid API key or endpoint); "
            "fell back to tiktoken."
        )
    else:
        warnings.append(
            "Estimate is tiktoken on assembled text/schemas. Switch counting "
            "method to Provider to match chat Input more closely "
            "(Anthropic, OpenAI, or Google)."
        )
    return warnings
