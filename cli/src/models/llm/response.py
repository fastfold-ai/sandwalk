"""Standardized LLM response dataclass."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class LLMResponse:
    """Standardized response from any LLM backend."""
    content: str
    model: str
    usage: dict = None
    raw: object = None
    content_blocks: list = None  # Raw content blocks from API (for tool use)
