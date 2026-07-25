"""Auto-generate short chat titles from the session's selected model."""

from __future__ import annotations

import logging
from collections.abc import Iterable
from dataclasses import dataclass

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

# Wait for two full turns (user+assistant × 2) so the title has real signal.
MIN_MESSAGES_FOR_LLM_TITLE = 4
# Still need at least one user turn before calling the model (force / short chats).
MIN_MESSAGES_FOR_FORCED_LLM_TITLE = 2
MAX_TITLE_PROMPT_MESSAGES = 6
MAX_TITLE_PROMPT_CHARS = 400

TITLE_SYSTEM_PROMPT = (
    "Generate a short, concise title (max 4 words) for this chat based on the user intent. "
    "Return only the title text — no quotes, labels, or explanation."
)


@dataclass(frozen=True)
class TitleResult:
    """Result of a title attempt.

    ``final`` is True only when the model produced a usable title — the session
    ``title_source`` should then become ``auto``. Interim/fallback titles keep
    ``title_source=pending`` so a later turn can upgrade them.
    """

    title: str
    final: bool = False


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
    """Legacy helper for display/CLI; auto-title gating uses ``title_source``."""
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


def conversation_messages(messages: Iterable[dict[str, str]]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for message in messages:
        role = str(message.get("role") or "").strip().lower()
        content = str(message.get("content") or "").strip()
        if role not in {"user", "assistant"} or not content:
            continue
        out.append({"role": role, "content": content})
    return out


def first_user_content(messages: Iterable[dict[str, str]]) -> str:
    for message in conversation_messages(messages):
        if message["role"] == "user":
            return message["content"]
    return ""


def should_attempt_llm_title(
    messages: Iterable[dict[str, str]], *, force: bool = False
) -> bool:
    count = len(conversation_messages(messages))
    if force:
        return count >= MIN_MESSAGES_FOR_FORCED_LLM_TITLE
    return count >= MIN_MESSAGES_FOR_LLM_TITLE


def build_title_prompt(
    messages: Iterable[dict[str, str]],
    *,
    max_messages: int = MAX_TITLE_PROMPT_MESSAGES,
    max_chars: int = MAX_TITLE_PROMPT_CHARS,
) -> str:
    prompt_lines: list[str] = []
    for message in conversation_messages(messages):
        content = message["content"]
        if len(content) > max_chars:
            content = content[: max_chars - 3].rstrip() + "..."
        prompt_lines.append(f"{message['role'].title()}: {content}")
        if len(prompt_lines) >= max_messages:
            break
    return "\n".join(prompt_lines)


def _title_llm_client():
    """Build an LLM client for the currently selected session model."""
    from agent.config import Config
    from models.llm import LLMClient

    config = Config.load()
    provider = str(config.get("llm.provider") or "anthropic").strip().lower()
    model = str(config.get("llm.model") or "").strip() or None
    api_key = config.llm_api_key(provider)
    if provider == "openai":
        base_url = config.llm_openai_base_url()
    else:
        base_url = config.llm_provider_base_url(provider)
    return LLMClient(
        provider=provider,
        model=model,
        api_key=api_key,
        base_url=base_url,
    )


def generate_session_title(
    messages: Iterable[dict[str, str]],
    *,
    fallback_query: str | None = None,
) -> TitleResult:
    """Generate a short title using the active session model.

    Uses a normal chat completion against whatever provider/model the user has
    selected. Falls back to a truncated first-user query when the model call is
    unavailable (``final=False`` so auto-title can retry later).
    """
    prompt = build_title_prompt(messages)
    fallback = fallback_title_from_query(
        fallback_query or first_user_content(messages)
    )
    if not prompt:
        return TitleResult(title=fallback, final=False)

    try:
        llm = _title_llm_client()
        response = llm.chat(
            TITLE_SYSTEM_PROMPT,
            [{"role": "user", "content": prompt}],
            temperature=0.2,
            max_tokens=32,
        )
        title = sanitize_generated_title(response.content)
        if title and not is_placeholder_title(title):
            return TitleResult(title=title, final=True)
        logger.debug(
            "Session title model returned empty/placeholder title (provider=%s model=%s)",
            getattr(llm, "provider", "?"),
            getattr(llm, "model", "?"),
        )
    except Exception as exc:
        # Title generation is best-effort — never break the session for it.
        logger.debug("Session title generation skipped: %s", exc)

    return TitleResult(title=fallback, final=False)
