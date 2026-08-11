"""Regression tests for empty adaptive-thinking block repair."""

from __future__ import annotations

from agent.deepagents_runtime.anthropic_thinking_patch import (
    _ensure_thinking_key,
    apply_anthropic_empty_thinking_patch,
)


def test_ensure_thinking_key_fills_missing_field():
    block = {"type": "thinking", "signature": "sig"}
    assert _ensure_thinking_key(block) == {
        "type": "thinking",
        "signature": "sig",
        "thinking": "",
    }


def test_ensure_thinking_key_preserves_existing_text():
    block = {"type": "thinking", "thinking": "plan", "signature": "sig"}
    assert _ensure_thinking_key(block)["thinking"] == "plan"


def test_ensure_thinking_key_ignores_non_thinking():
    block = {"type": "text", "text": "hi"}
    assert _ensure_thinking_key(block) is block


def test_apply_patch_is_idempotent():
    apply_anthropic_empty_thinking_patch()
    apply_anthropic_empty_thinking_patch()
    import langchain_anthropic.chat_models as mod

    # Format path restores missing thinking for already-corrupted history.
    from langchain_core.messages import AIMessage, HumanMessage

    system, messages = mod._format_messages(
        [
            HumanMessage("hi"),
            AIMessage(
                content=[
                    {"type": "thinking", "signature": "sig-only"},
                    {"type": "text", "text": "hello"},
                ]
            ),
        ]
    )
    del system
    thinking = messages[1]["content"][0]
    assert thinking["type"] == "thinking"
    assert thinking.get("thinking") == ""
    assert thinking.get("signature") == "sig-only"
