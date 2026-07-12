"""Auto-generate short chat titles the same way as FastFold Cloud Agents."""

from __future__ import annotations

import logging
from typing import Iterable

logger = logging.getLogger("agent_server.title")

PLACEHOLDER_TITLES = frozenset(
    {
        "untitled",
        "untitled session",
        "untitled thread",
        "new chat",
        "new agent",
        "new agent session",
        "new research session",
    }
)

TITLE_SYSTEM_PROMPT = (
    "Generate a short, concise title (max 4 words) for this chat based on the user intent."
)


def sanitize_generated_title(raw_title: str | None) -> str:
    title = (raw_title or "").strip()
    if not title:
        return ""
    quote_pairs = {"'": "'", '"': '"', "“": "”", "‘": "’"}
    while len(title) >= 2 and title[0] in quote_pairs and title[-1] == quote_pairs[title[0]]:
        title = title[1:-1].strip()
    # Keep titles compact for sidebar display.
    title = " ".join(title.split())
    if len(title) > 64:
        title = title[:61].rstrip() + "..."
    return title


def is_placeholder_title(title: str | None) -> bool:
    value = (title or "").strip().lower()
    if not value or value in PLACEHOLDER_TITLES:
        return True
    return (
        "greeting chat" in value
        or "casual greeting" in value
        or value in {"general conversation", "small talk"}
    )


def fallback_title_from_query(query: str | None) -> str:
    generated = " ".join(str(query or "").split()).strip()
    if not generated:
        return ""
    if len(generated) > 64:
        generated = generated[:61].rstrip() + "..."
    return generated


def _title_model_for_provider(provider: str, configured_model: str | None) -> str:
    provider_name = str(provider or "").strip().lower()
    if provider_name == "openai":
        return "gpt-4o-mini"
    if provider_name == "anthropic":
        return "claude-haiku-4-5-20251001"
    return str(configured_model or "").strip() or "gpt-4o-mini"


def build_title_prompt(messages: Iterable[dict[str, str]]) -> str:
    prompt_lines: list[str] = []
    for message in messages:
        role = str(message.get("role") or "").strip().lower()
        content = str(message.get("content") or "").strip()
        if role not in {"user", "assistant"} or not content:
            continue
        prompt_lines.append(f"{role.title()}: {content}")
        if len(prompt_lines) >= 2:
            break
    return "\n".join(prompt_lines)


def generate_session_title(
    messages: Iterable[dict[str, str]],
    *,
    fallback_query: str | None = None,
) -> str:
    """Generate a short title from the first user/assistant exchange.

    Uses the configured FastFold LLM provider. Falls back to a truncated query
    when the model call is unavailable.
    """
    prompt = build_title_prompt(messages)
    if not prompt:
        return fallback_title_from_query(fallback_query)

    try:
        from agent.config import Config
        from agent.session import Session

        session = Session(config=Config.load())
        provider = str(session.config.get("llm.provider") or "anthropic").strip().lower()
        configured_model = str(session.config.get("llm.model") or "").strip() or None
        title_model = _title_model_for_provider(provider, configured_model)
        session.set_model(title_model, provider=provider)
        llm = session.get_llm()
        response = llm.chat(
            TITLE_SYSTEM_PROMPT,
            [{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=16,
        )
        title = sanitize_generated_title(response.content)
        if title:
            return title
    except Exception:
        logger.exception("Failed to generate session title via LLM")

    return fallback_title_from_query(fallback_query)
