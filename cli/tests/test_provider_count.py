"""Provider-native prompt-budget token counting dispatch."""

from __future__ import annotations

from agent_server.prompt_budget_service.provider_count import (
    _parse_tools,
    _sanitize_google_schema,
    count_google_input_tokens,
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


def test_google_schema_sanitizer_removes_json_schema_metadata():
    from google.genai import types

    schema = _sanitize_google_schema(
        {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "$comment": "unsupported metadata",
                }
            },
        }
    )

    assert "$schema" not in schema
    assert "$comment" not in schema["properties"]["query"]
    declaration = types.FunctionDeclaration(name="search", parameters=schema)
    assert declaration.parameters is not None
    assert "query" in (declaration.parameters.properties or {})


def test_google_schema_failure_falls_back_without_raising(monkeypatch):
    from types import SimpleNamespace

    from google import genai
    from google.genai import types

    def reject_schema(**kwargs):
        raise ValueError("unsupported schema")

    class Client:
        def __init__(self, **kwargs):
            self.models = SimpleNamespace(
                count_tokens=lambda **count_kwargs: SimpleNamespace(
                    total_tokens=17
                )
            )

    monkeypatch.setattr(types, "FunctionDeclaration", reject_schema)
    monkeypatch.setattr(genai, "Client", Client)

    count = count_google_input_tokens(
        model="gemini-test",
        api_key="test-key",
        system_parts=["system"],
        tool_texts=[
            '{"name":"search","input_schema":{"$schema":"unsupported"}}'
        ],
    )

    assert count == 17


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
