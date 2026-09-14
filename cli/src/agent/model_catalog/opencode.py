"""OpenCode Zen model id handling: API routing, labels, denylist."""

from __future__ import annotations

# OpenCode Zen models that speak the Anthropic Messages API
# (https://opencode.ai/zen/v1/messages). GPT models use Responses API;
# open models (Kimi, GLM, DeepSeek, MiniMax, …) use chat completions.
_OPENCODE_ANTHROPIC_PREFIXES = ("claude-", "qwen")

# Discovered OpenCode Zen ids that fail end-to-end (upstream 400 / unsupported
# format). Filtered out of /v1/models so they never appear in the UI.
OPENCODE_UNSUPPORTED_MODELS: frozenset[str] = frozenset(
    {
        "claude-sonnet-4",  # not on Zen full model list
        "gemini-3-flash",  # Zen Gemini path: missing contents
        "gemini-3.1-pro",  # Zen Gemini path: missing contents
        "gpt-5",  # upstream request failed
        "gpt-5-codex",  # upstream request failed
        "gpt-5.1-codex",  # upstream request failed
        "gpt-5.1-codex-max",  # upstream request failed
        "gpt-5.1-codex-mini",  # upstream request failed
        "gpt-5.2-codex",  # upstream request failed
        "gpt-5.3-codex-spark",  # not supported for openai format
    }
)


def opencode_model_is_supported(model_id: str | None) -> bool:
    """Return False when a discovered OpenCode Zen id is denylisted."""
    value = str(model_id or "").strip()
    if not value:
        return False
    return value not in OPENCODE_UNSUPPORTED_MODELS


def _deepseek_flash_display_label(model_id: str) -> str | None:
    """Dated Flash labels when the slug encodes 0423 / 0731 / latest.

    OpenRouter's undated ``deepseek/deepseek-v4-flash`` is the Apr 2026
    preview (0423). Bare ``deepseek-v4-flash`` (native DeepSeek / OpenCode)
    is left unlabeled here so it stays "DeepSeek V4 Flash".
    """
    raw = str(model_id or "").strip().lower()
    if raw.startswith("~"):
        raw = raw[1:]
    slug = raw.rsplit("/", 1)[-1]
    if slug in {
        "deepseek-v4-flash-0731",
        "deepseek-v4-flash-20260731",
    }:
        return "DeepSeek V4 Flash 0731"
    if slug in {
        "deepseek-v4-flash-0423",
        "deepseek-v4-flash-20260423",
    }:
        return "DeepSeek V4 Flash 0423"
    if slug == "deepseek-v4-flash-latest":
        return "DeepSeek V4 Flash Latest"
    # OpenRouter vendor path: undated flash slug == 0423 preview.
    if slug == "deepseek-v4-flash" and raw.startswith("deepseek/"):
        return "DeepSeek V4 Flash 0423"
    return None


def format_discovered_model_label(model_id: str) -> str:
    """Turn a raw model id like ``kimi-k2.7-code`` into ``Kimi K2.7 Code``.

    Known product acronyms (``gpt``, ``glm``, …) stay fully uppercase.
    DeepSeek V4 Flash revisions keep the 0423 / 0731 date so OpenRouter and
    Qwen Cloud rows do not collapse to the same display name.
    """
    raw = str(model_id or "").strip()
    if not raw:
        return raw
    dated = _deepseek_flash_display_label(raw)
    if dated is not None:
        return dated
    # OpenRouter / Together style ``vendor/model`` → label the model slug only.
    slug = raw.rsplit("/", 1)[-1]
    # Tokens that should stay ALL CAPS in UI labels (GPT 5.1, GLM 5, …).
    acronyms = {"gpt", "glm", "aws", "api", "llm", "ml"}
    parts = slug.replace("_", "-").split("-")
    out: list[str] = []
    for part in parts:
        if not part:
            continue
        lower = part.lower()
        if lower in acronyms:
            out.append(lower.upper())
            continue
        # Keep version-like tokens readable (k2.7 -> K2.7, v4 -> V4).
        out.append(part[:1].upper() + part[1:])
    # Prefer the DeepSeek brand casing when the slug starts with deepseek.
    label = " ".join(out) or raw
    if label.lower().startswith("deepseek "):
        return "DeepSeek " + label[len("Deepseek ") :]
    return label


def opencode_model_uses_anthropic(model_id: str) -> bool:
    """Return True when an OpenCode Zen model must use the Anthropic Messages API."""
    normalized = str(model_id or "").strip().lower()
    return any(normalized.startswith(prefix) for prefix in _OPENCODE_ANTHROPIC_PREFIXES)


def opencode_model_uses_responses_api(model_id: str) -> bool:
    """Return True when an OpenCode Zen model must use OpenAI ``/v1/responses``."""
    normalized = str(model_id or "").strip().lower()
    return normalized.startswith("gpt-")


def opencode_anthropic_base_url(openai_base_url: str) -> str:
    """Convert OpenAI-compatible Zen base URL to Anthropic SDK base URL.

    OpenAI SDK expects ``.../zen/v1`` (appends ``/chat/completions`` or ``/responses``).
    Anthropic SDK expects ``.../zen`` (appends ``/v1/messages``).
    """
    base = str(openai_base_url or "").strip().rstrip("/")
    if base.endswith("/v1"):
        return base[:-3]
    return base


def openai_model_requires_responses_api(model_id: str) -> bool:
    """Return True when an OpenAI cloud model should use ``/v1/responses``.

    Codex models reject chat completions entirely. GPT-5 / o-series reject
    function tools + non-none reasoning_effort on chat completions — agent
    runs always use tools, so route those through Responses as well.
    """
    value = str(model_id or "").strip().lower()
    if not value:
        return False
    if value.startswith("o1") or value.startswith("o3") or value.startswith("o4"):
        return True
    if not value.startswith("gpt-"):
        return False
    if "codex" in value:
        return True
    # GPT-5 / GPT-6 family (incl. 5.4 / 5.5 / 5.6 / Astra and -pro/-mini/-nano/-sol/…)
    if value.startswith("gpt-5") or value.startswith("gpt-6"):
        # Chat-only / non-reasoning GPT-5 variants stay on chat completions.
        if "chat" in value and "latest" in value:
            return False
        return True
    return False
