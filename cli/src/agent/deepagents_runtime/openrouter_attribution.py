"""OpenRouter app-attribution constants for Sandwalk rankings."""

from __future__ import annotations

OPENROUTER_APP_URL = "https://sandwalk.sh"
OPENROUTER_APP_TITLE = "Sandwalk"
OPENROUTER_APP_CATEGORIES = ("cli-agent", "personal-agent")


def openrouter_attribution_headers() -> dict[str, str]:
    """Headers required for OpenRouter app rankings and marketplace categories."""
    return {
        "HTTP-Referer": OPENROUTER_APP_URL,
        "X-OpenRouter-Title": OPENROUTER_APP_TITLE,
        "X-Title": OPENROUTER_APP_TITLE,
        "X-OpenRouter-Categories": ",".join(OPENROUTER_APP_CATEGORIES),
    }
