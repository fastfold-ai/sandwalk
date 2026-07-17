"""Chat model factory dispatch and OpenAI tool-count capping."""

from __future__ import annotations

from agent.deepagents_runtime.chat_model_anthropic import build_anthropic_chat_model
from agent.deepagents_runtime.chat_model_compatible import build_compatible_chat_model
from agent.deepagents_runtime.chat_model_google import build_google_chat_model
from agent.deepagents_runtime.chat_model_moonshot import build_moonshot_chat_model
from agent.deepagents_runtime.chat_model_openai import build_openai_chat_model

# Leave headroom below the OpenAI 128-tool ceiling for deepagents' built-in
# tools (write_todos, filesystem ops, task, execute).
OPENAI_TOOL_BUDGET = 116
# Always keep sandbox / discovery tools when truncating for OpenAI.
_PINNED_TOOL_NAMES = (
    "run_python",
    "run_r",
    "shell_run",
    "search_tools",
    "sandbox_status",
    "sandbox_start",
    "sandbox_stop",
)


def provider_needs_openai_tool_cap(provider: str | None) -> bool:
    """Return True when the provider enforces OpenAI's ≤128 tools limit."""
    return str(provider or "").strip().lower() == "openai"


def finalize_tools_for_provider(tools: list, provider: str | None) -> list:
    """Apply provider-specific tool-list limits after domain + MCP assembly."""
    if not provider_needs_openai_tool_cap(provider):
        return list(tools)
    return _cap_tools_for_openai(tools)


def build_chat_model(config, *, streaming: bool = True):
    """Create a LangChain chat model from Fastfold config via ``init_chat_model``.

    Supports ``anthropic``, ``openai`` (including OpenAI-compatible local
    endpoints), ``google`` via the native Google GenAI SDK, ``moonshot`` via
    ChatMoonshot, and other first-party OpenAI-compatible providers (xAI,
    NVIDIA, OpenCode Zen).
    """
    provider = str(config.get("llm.provider", "openai") or "openai").strip().lower()
    temperature = float(config.get("llm.temperature", 0.1))

    if provider == "anthropic":
        return build_anthropic_chat_model(config, temperature=temperature)
    if provider == "openai":
        return build_openai_chat_model(config, temperature=temperature)
    if provider == "google":
        return build_google_chat_model(config, temperature=temperature)
    if provider == "moonshot":
        return build_moonshot_chat_model(config, temperature=temperature)
    return build_compatible_chat_model(config, provider, temperature=temperature)


def _cap_tools_for_openai(tools: list, max_total: int = OPENAI_TOOL_BUDGET) -> list:
    """Cap the domain tool list for OpenAI while keeping the sandbox tools."""
    if len(tools) <= max_total:
        return list(tools)

    by_name = {getattr(t, "name", ""): t for t in tools}
    selected = list(tools[:max_total])
    selected_names = {getattr(t, "name", "") for t in selected}

    for pinned in _PINNED_TOOL_NAMES:
        spec = by_name.get(pinned)
        if spec is None or pinned in selected_names:
            continue
        replace_idx = next(
            (
                idx
                for idx in range(len(selected) - 1, -1, -1)
                if getattr(selected[idx], "name", "") not in _PINNED_TOOL_NAMES
            ),
            None,
        )
        if replace_idx is not None:
            selected_names.discard(getattr(selected[replace_idx], "name", ""))
            selected[replace_idx] = spec
            selected_names.add(pinned)
    return selected
