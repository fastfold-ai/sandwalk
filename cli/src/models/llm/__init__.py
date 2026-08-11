"""
Unified LLM client: supports Anthropic, OpenAI, local models, and CellType models.

Provides a consistent interface regardless of backend. CellType's own models
(GlueLM, C2S, etc.) are imported directly as Python modules when available,
falling back to API calls if served remotely.
"""

from __future__ import annotations

import time  # noqa: F401  (exposed as models.llm.time for test patching)

from models.llm.client import LLMClient
from models.llm.helpers import (
    _anthropic_temperature_kwargs,
    _openai_temperature_kwargs,
    _openai_token_limit_kwargs,
    logger,
)
from models.llm.pricing import MODEL_PRICING, UsageTracker
from models.llm.response import LLMResponse

__all__ = [
    "LLMClient",
    "LLMResponse",
    "MODEL_PRICING",
    "UsageTracker",
    "logger",
    "_openai_token_limit_kwargs",
    "_openai_temperature_kwargs",
    "_anthropic_temperature_kwargs",
]
