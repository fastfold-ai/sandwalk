"""Resolve stored effort + Fast toggle into the per-provider API value."""

from __future__ import annotations

from typing import Any

from agent.model_catalog.reasoning_support import (
    normalize_reasoning_effort,
    openrouter_model_reasoning_mandatory,
)


def openai_reasoning_effort_floor(model_id: str | None) -> str:
    """Lowest ``reasoning_effort`` accepted by a given OpenAI model.

    Most GPT-5 models accept ``none``. Pro variants only allow medium+;
    classic ``gpt-5-mini`` / ``gpt-5-nano`` allow ``minimal`` but not ``none``.
    """
    value = str(model_id or "").strip().lower()
    if not value:
        return "none"
    if "pro" in value:
        return "medium"
    # Bare gpt-5-mini / gpt-5-nano (not gpt-5.4-mini / gpt-5.4-nano).
    if value in {"gpt-5-mini", "gpt-5-nano"} or value.startswith(
        ("gpt-5-mini-", "gpt-5-nano-")
    ):
        return "minimal"
    return "none"


_OPENAI_EFFORT_RANK = {
    "none": 0,
    "minimal": 1,
    "low": 2,
    "medium": 3,
    "high": 4,
    "xhigh": 5,
}


def clamp_openai_reasoning_effort(model_id: str | None, effort: str) -> str:
    """Raise effort up to the model floor when the requested level is too low."""
    floor = openai_reasoning_effort_floor(model_id)
    raw = str(effort or "").strip().lower() or floor
    if _OPENAI_EFFORT_RANK.get(raw, 3) < _OPENAI_EFFORT_RANK.get(floor, 0):
        return floor
    return raw


def effective_reasoning_effort(
    *,
    effort: str | None,
    fast: bool = False,
    model_id: str | None = None,
) -> str:
    """Resolve stored effort + Fast toggle to the API reasoning_effort value."""
    if fast:
        return openai_reasoning_effort_floor(model_id)
    return clamp_openai_reasoning_effort(model_id, normalize_reasoning_effort(effort))


def effective_anthropic_effort(
    *,
    effort: str | None,
    fast: bool = False,
) -> str:
    """Map UI effort/Fast onto Anthropic ``effort`` (no ``none`` level)."""
    if fast:
        return "low"
    raw = normalize_reasoning_effort(effort)
    if raw == "none":
        return "low"
    return raw


def effective_gemini_thinking_level(
    *,
    effort: str | None,
    fast: bool = False,
) -> str:
    """Map UI effort/Fast onto Gemini 3+ ``thinking_level``."""
    if fast:
        return "minimal"
    raw = normalize_reasoning_effort(effort)
    if raw in {"none", "low"}:
        return "low" if raw == "low" else "minimal"
    if raw == "high":
        return "high"
    return "medium"


def effective_xai_reasoning_effort(
    *,
    effort: str | None,
    fast: bool = False,
    model_id: str | None = None,
) -> str:
    """Map UI effort/Fast onto xAI ``reasoning_effort``.

    ``grok-4.5`` accepts only low/medium/high (cannot disable). ``grok-4.3``
    also accepts ``none``. Fast maps to the lowest allowed level.
    """
    value = str(model_id or "").strip().lower()
    # 4.5 cannot disable reasoning; 4.3 / 4.20 accept none.
    allows_none = "4.5" not in value
    if fast:
        return "none" if allows_none else "low"
    raw = normalize_reasoning_effort(effort)
    if raw == "none" and not allows_none:
        return "low"
    return raw


def effective_moonshot_thinking(
    *,
    effort: str | None,
    fast: bool = False,
) -> bool:
    """Map UI effort/Fast onto Moonshot ChatMoonshot ``thinking``.

    Fast → thinking off; Low/Medium/High → thinking on.
    """
    if fast:
        return False
    raw = normalize_reasoning_effort(effort)
    return raw != "none"


def effective_unsloth_enable_thinking(
    *,
    effort: str | None,
    fast: bool = False,
) -> bool:
    """Map UI effort/Fast onto Unsloth ``enable_thinking``.

    Fast → false; Low/Medium/High → true (Unsloth default is on).
    """
    if fast:
        return False
    raw = normalize_reasoning_effort(effort)
    return raw != "none"


def effective_openrouter_reasoning(
    *,
    effort: str | None,
    fast: bool = False,
    model_id: str | None = None,
) -> dict[str, Any]:
    """Map UI effort/Fast onto OpenRouter ``reasoning`` (``effort`` key).

    Uses the unified OpenRouter shape:
    ``{"effort": "none"|"low"|"medium"|"high"|...}``.

    OpenAI / xAI ids reuse their native floor rules; mandatory models
    (Gemini 2.5 Pro, Grok 4.5) never send ``none``.
    """
    value = str(model_id or "").strip().lower()
    slug = value.split("/", 1)[-1] if value else ""
    vendor = value.split("/", 1)[0] if "/" in value else ""

    if vendor == "openai" or slug.startswith(("gpt-5", "o1", "o3", "o4")):
        level = effective_reasoning_effort(
            effort=effort, fast=fast, model_id=slug
        )
        return {"effort": level}

    if vendor in {"x-ai", "xai"} or slug.startswith("grok-"):
        level = effective_xai_reasoning_effort(
            effort=effort, fast=fast, model_id=slug
        )
        return {"effort": level}

    mandatory = openrouter_model_reasoning_mandatory(model_id)
    if fast:
        return {"effort": "low" if mandatory else "none"}
    raw = normalize_reasoning_effort(effort)
    if raw == "none" and mandatory:
        return {"effort": "low"}
    return {"effort": raw}
