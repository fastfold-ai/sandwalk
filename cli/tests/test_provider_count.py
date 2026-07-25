"""Provider-native prompt-budget token counting dispatch."""

from __future__ import annotations

from agent_server.prompt_budget_service.provider_count import (
    _parse_tools,
    count_provider_input_tokens,
)


def test_parse_tools_accepts_anthropic_json_and_fallback():
    tools = _parse_tools(
        [
            '{"name":"ls","description":"list","input_schema":{"type":"object"}}',
            "not-json",
            "",
        ]
    )
    assert tools[0]["name"] == "ls"
    assert tools[1]["name"] == "tool"
    assert len(tools) == 2


def test_dispatch_returns_none_without_keys():
    tokens, label = count_provider_input_tokens(
        provider="anthropic",
        model="claude-opus-5",
        api_key=None,
        system_parts=["hi"],
        tool_texts=[],
    )
    assert tokens is None
    assert label is None

    tokens, label = count_provider_input_tokens(
        provider="xai",
        model="grok-3",
        api_key="sk-test",
        system_parts=["hi"],
        tool_texts=[],
    )
    assert tokens is None
    assert label is None


def test_openai_skips_local_placeholder_keys():
    tokens, label = count_provider_input_tokens(
        provider="openai",
        model="gpt-4o",
        api_key="ollama",
        system_parts=["You are helpful."],
        tool_texts=[],
    )
    assert tokens is None
    assert label is None
