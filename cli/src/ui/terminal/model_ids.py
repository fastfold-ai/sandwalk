"""Model catalog and OpenAI-managed-host helpers for the terminal's model switcher."""

from __future__ import annotations

from urllib.parse import urlparse

from agent.model_catalog import terminal_available_models

# Models available for switching, grouped by provider
AVAILABLE_MODELS = terminal_available_models()

_ANTHROPIC_MODEL_IDS = {m[0] for m in AVAILABLE_MODELS.get("anthropic", [])}
_BOLTZ_SKILL_SOURCE = "fastfold-ai/skills@skills/boltz"
_BOLTZ_INSTALL_SCRIPT = "set -euo pipefail; curl -fsSL https://install.boltz.bio/boltz-api/install.sh | sh"


def _is_openai_managed_base_url(base_url: str | None) -> bool:
    """Return True for OpenAI-managed API hosts."""
    value = str(base_url or "").strip()
    if not value:
        return True
    try:
        host = (urlparse(value).hostname or "").strip().lower()
    except Exception:
        return False
    if not host:
        return False
    return host == "api.openai.com" or host.endswith(".openai.com")
