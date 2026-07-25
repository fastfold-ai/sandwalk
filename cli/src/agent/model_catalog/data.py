"""Static cloud model catalog data (provider → model rows)."""

from __future__ import annotations

from typing import TypedDict


class CatalogModel(TypedDict):
    id: str
    label: str
    description: str
    provider: str


# Static Anthropic + OpenAI cloud catalog (excludes OpenAI-compatible profile entry).
# New-generation models come first (enabled by default); legacy models remain in
# the catalog but are disabled by default (see DEFAULT_DISABLED_MODELS).
AVAILABLE_MODELS: dict[str, list[tuple[str, str, str]]] = {
    "anthropic": [
        (
            "claude-opus-5",
            "Opus 5",
            "Powerful model for complex agentic coding and enterprise work (1M context)",
        ),
        ("claude-sonnet-5", "Sonnet 5", "Best combination of speed and intelligence"),
        ("claude-fable-5", "Fable 5", "Next-generation intelligence for long-running agents"),
        ("claude-sonnet-4-6", "Sonnet 4.6", "Fast, balanced Sonnet for most tasks"),
        # Legacy (disabled by default)
        ("claude-opus-4-8", "Opus 4.8", "Previous-generation Opus"),
        ("claude-sonnet-4-5-20250929", "Sonnet 4.5", "Previous-generation Sonnet"),
        ("claude-haiku-4-5-20251001", "Haiku 4.5", "Fastest previous-generation Anthropic option"),
        ("claude-opus-4-6", "Opus 4.6", "Previous-generation Opus"),
    ],
    "openai": [
        ("gpt-5.6-sol", "GPT-5.6 Sol", "High-speed frontier model for coding"),
        ("gpt-5.6-terra", "GPT-5.6 Terra", "Balanced GPT-5.6 for general professional work"),
        ("gpt-5.5", "GPT-5.5", "Frontier model for coding and professional work"),
        ("gpt-5.3-codex", "Codex 5.3", "Specialized OpenAI coding model (Responses API)"),
        # Legacy (disabled by default)
        ("gpt-5.5-pro", "GPT-5.5 Pro", "Smarter, more precise GPT-5.5 variant"),
        ("gpt-5.4", "GPT-5.4", "Previous-generation model for coding and professional work"),
        ("gpt-5.4-pro", "GPT-5.4 Pro", "Smarter, more precise GPT-5.4 variant"),
        ("gpt-5.4-mini", "GPT-5.4 Mini", "Strong mini model for coding, computer use, and subagents"),
        ("gpt-5.4-nano", "GPT-5.4 Nano", "Cheapest GPT-5.4-class model for high-volume simple tasks"),
        ("gpt-5-mini", "GPT-5 Mini", "Near-frontier model for cost-sensitive low-latency workloads"),
        ("gpt-5-nano", "GPT-5 Nano", "Cheapest GPT-5-class model for simple high-volume tasks"),
    ],
    "xai": [
        ("grok-4.5", "Grok 4.5", "Most intelligent and fastest xAI model"),
        ("grok-4.3", "Grok 4.3", "Fast general-purpose xAI model with 1M context"),
        ("grok-4.20", "Grok 4.20", "Reasoning-capable xAI model"),
    ],
    "google": [
        (
            "gemini-3.1-pro-preview",
            "Gemini 3.1 Pro",
            "Most intelligent Gemini for multimodal reasoning",
        ),
        ("gemini-3.5-flash", "Gemini 3.5 Flash", "Frontier-class Gemini at a fraction of the cost"),
        ("gemini-3.1-flash-lite", "Gemini 3.1 Flash-Lite", "High-volume, cost-sensitive Gemini model"),
    ],
    "moonshot": [
        (
            "kimi-k3",
            "Kimi K3",
            "Frontier Kimi with 1M context, vision, and deep reasoning",
        ),
        (
            "kimi-k2.6",
            "Kimi K2.6",
            "Multimodal Kimi with thinking and non-thinking modes (256k)",
        ),
        (
            "kimi-k2.7-code",
            "Kimi K2.7 Code",
            "Coding-focused Kimi with always-on thinking (256k)",
        ),
        (
            "kimi-k2.7-code-highspeed",
            "Kimi K2.7 Code Highspeed",
            "Faster Kimi K2.7 Code variant (~180 tok/s)",
        ),
        # Legacy (disabled by default; sunsetting for new users)
        (
            "kimi-k2.5",
            "Kimi K2.5",
            "Previous-generation multimodal Kimi (256k)",
        ),
    ],
    "nvidia": [
        (
            "nvidia/nemotron-3-ultra-550b-a55b",
            "Nemotron 3 Ultra 550B",
            "NVIDIA flagship reasoning model (NIM endpoint)",
        ),
    ],
    "deepseek": [
        (
            "deepseek-v4-flash",
            "DeepSeek V4 Flash",
            "Fast DeepSeek model for everyday agent work",
        ),
        (
            "deepseek-v4-pro",
            "DeepSeek V4 Pro",
            "Higher-capability DeepSeek for harder reasoning",
        ),
    ],
    "minimax": [
        (
            "MiniMax-M2.5",
            "MiniMax M2.5",
            "MiniMax flagship agent-capable model",
        ),
    ],
    "mistral": [
        (
            "mistral-large-latest",
            "Mistral Large",
            "Mistral flagship model for complex work",
        ),
        (
            "mistral-small-latest",
            "Mistral Small",
            "Faster, lower-cost Mistral model",
        ),
    ],
    "qwen": [
        (
            "qwen3-max",
            "Qwen3 Max",
            "Alibaba Qwen flagship for general agent work",
        ),
    ],
    "together": [
        (
            "thinkingmachines/Inkling",
            "Inkling · via Together",
            "Thinking Machines Inkling — multimodal (image + audio) via Together AI",
        ),
        (
            "zai-org/GLM-5.2",
            "GLM-5.2 · via Together",
            "Z AI GLM-5.2 via Together AI",
        ),
        (
            "moonshotai/Kimi-K2.7-Code",
            "Kimi K2.7 Code · via Together",
            "Moonshot Kimi K2.7 Code via Together AI",
        ),
        (
            "moonshotai/Kimi-K2.6",
            "Kimi K2.6 · via Together",
            "Moonshot Kimi K2.6 via Together AI",
        ),
        (
            "deepseek-ai/DeepSeek-V4-Pro",
            "DeepSeek V4 Pro · via Together",
            "DeepSeek V4 Pro via Together AI",
        ),
        # Llama 4 (Maverick/Scout) is dedicated-endpoint-only on Together now
        # (HTTP 400 model_not_available on serverless) — not curated.
    ],
}

# Bump when the default-enabled set changes so existing configs get migrated once.
CATALOG_DEFAULTS_VERSION = 4

# Models present in the catalog but hidden by default. Users can re-enable them
# from Dashboard → Models; toggling simply removes them from the hidden list.
DEFAULT_DISABLED_MODELS: frozenset[str] = frozenset(
    {
        "claude-opus-4-8",
        "claude-sonnet-4-5-20250929",
        "claude-haiku-4-5-20251001",
        "claude-opus-4-6",
        "gpt-5.5-pro",
        "gpt-5.4",
        "gpt-5.4-pro",
        "gpt-5.4-mini",
        "gpt-5.4-nano",
        "gpt-5-mini",
        "gpt-5-nano",
        "kimi-k2.5",
    }
)

CUSTOM_OPENAI_COMPATIBLE_ENTRY = (
    "__custom_openai_compatible__",
    "OpenAI-compatible profiles",
    "Use, add, or edit Ollama/Unsloth/oMLX/custom OpenAI-compatible profiles",
)
