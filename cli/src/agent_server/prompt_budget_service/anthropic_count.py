"""Backward-compatible Anthropic counting helper.

Prefer ``provider_count.count_provider_input_tokens`` for new call sites.
"""

from __future__ import annotations

from agent_server.prompt_budget_service.provider_count import (
    count_anthropic_input_tokens,
)

__all__ = ["count_anthropic_input_tokens"]
