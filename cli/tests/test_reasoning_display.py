"""Coverage for Effort / Fast display labels used by the CLI banner/toolbar."""

from __future__ import annotations

from types import SimpleNamespace

from agent.model_catalog.reasoning_display import (
    config_selected_effort_label,
    format_reasoning_effort_label,
    selected_reasoning_effort_label,
)


def test_format_reasoning_effort_label():
    assert format_reasoning_effort_label(effort="high", fast=False) == "High"
    assert format_reasoning_effort_label(effort="medium", fast=True) == "Medium · Fast"
    assert format_reasoning_effort_label(effort=None, fast=False) == "Medium"


def test_selected_reasoning_effort_label_when_unsupported():
    assert (
        selected_reasoning_effort_label(
            {},
            "openrouter",
            "openai/gpt-4o-mini",
        )
        is None
    )


def test_selected_reasoning_effort_label_openrouter_glm():
    store = {
        "openrouter:z-ai/glm-5.2": {"effort": "high", "fast": False},
    }
    assert (
        selected_reasoning_effort_label(
            store,
            "openrouter",
            "z-ai/glm-5.2",
        )
        == "High"
    )
    store["openrouter:z-ai/glm-5.2"] = {"effort": "medium", "fast": True}
    assert (
        selected_reasoning_effort_label(
            store,
            "openrouter",
            "z-ai/glm-5.2",
        )
        == "Medium · Fast"
    )


def test_config_selected_effort_label_defaults_and_store():
    cfg = SimpleNamespace(
        get=lambda key, default=None: {
            "llm.provider": "openrouter",
            "llm.model": "z-ai/glm-5.2",
            "llm.reasoning_effort": "medium",
            "llm.reasoning_fast": False,
            "llm.model_reasoning": {
                "openrouter:z-ai/glm-5.2": {"effort": "low", "fast": False},
            },
        }.get(key, default),
        get_openai_profile=lambda: {},
    )
    assert config_selected_effort_label(cfg) == "Low"

    cfg_no_effort = SimpleNamespace(
        get=lambda key, default=None: {
            "llm.provider": "openrouter",
            "llm.model": "openai/gpt-4o-mini",
            "llm.reasoning_effort": "medium",
            "llm.reasoning_fast": False,
            "llm.model_reasoning": {},
        }.get(key, default),
        get_openai_profile=lambda: {},
    )
    assert config_selected_effort_label(cfg_no_effort) is None
