"""Anthropic chat model bounds stalled requests instead of the SDK's 10 min default."""

from __future__ import annotations

from unittest.mock import patch

import langchain.chat_models as lc_chat_models

from agent.deepagents_runtime import chat_model_anthropic


class _Config:
    def __init__(self, values: dict | None = None):
        self._values = values or {}

    def get(self, key, default=None):
        return self._values.get(key, default)

    def llm_api_key(self, provider):  # noqa: ARG002
        return "test-key-not-real"


def test_anthropic_model_gets_bounded_timeout_and_retries():
    captured: dict = {}

    def fake_init(model, **kwargs):
        captured["model"] = model
        captured.update(kwargs)
        return object()

    with patch.object(lc_chat_models, "init_chat_model", side_effect=fake_init):
        chat_model_anthropic.build_anthropic_chat_model(
            _Config({"llm.model": "claude-sonnet-5"}), temperature=0.2
        )

    assert captured["model"] == "anthropic:claude-sonnet-5"
    assert captured["max_retries"] == 5
    assert captured["timeout"] == chat_model_anthropic.ANTHROPIC_REQUEST_TIMEOUT_S
    assert 0 < captured["timeout"] <= 300
