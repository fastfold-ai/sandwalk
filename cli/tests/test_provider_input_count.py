"""Provider token counters with the vendor SDKs replaced by fakes."""

from __future__ import annotations

import sys
from types import ModuleType, SimpleNamespace

from agent_server.prompt_budget_service import provider_count as pc


def test_parse_helpers():
    tools = pc._parse_tools(["", "not-json", '{"name": "fold"}', '{"nope": 1}'])
    assert tools[0]["name"] == "tool"
    assert tools[1]["name"] == "fold"
    assert pc._system_text(["  a ", "", "b"]) == "a\n\nb"
    assert pc._sanitize_google_schema({"$schema": "x", "type": "object", "items": [{"$id": 1, "n": 2}]}) == {
        "type": "object",
        "items": [{"n": 2}],
    }
    assert pc._sanitize_google_schema(["a"]) == ["a"]
    assert pc._openai_count_base_url("") is None
    assert pc._openai_count_base_url("http://127.0.0.1:9931/v1") is None
    assert "api.openai.com" in pc._openai_count_base_url("https://api.openai.com/v1")


def test_count_providers(monkeypatch):
    assert pc.count_anthropic_input_tokens(model="", api_key="k", system_parts=[], tool_texts=[]) is None
    assert pc.count_openai_input_tokens(model="m", api_key="local", system_parts=[], tool_texts=[]) is None
    assert pc.count_openai_input_tokens(
        model="m", api_key="sk", system_parts=[], tool_texts=[], base_url="http://localhost/v1"
    ) is None
    assert pc.count_google_input_tokens(model="m", api_key="", system_parts=[], tool_texts=[]) is None

    anthropic = ModuleType("anthropic")

    class _Messages:
        def count_tokens(self, **kwargs):
            if kwargs["model"] == "boom":
                raise RuntimeError("down")
            return SimpleNamespace(input_tokens=11)

    class _Anthropic:
        def __init__(self, api_key):
            self.messages = _Messages()

    anthropic.Anthropic = _Anthropic
    monkeypatch.setitem(sys.modules, "anthropic", anthropic)

    openai = ModuleType("openai")

    class _Count:
        def count(self, **kwargs):
            if kwargs["model"] == "boom":
                raise RuntimeError("down")
            return SimpleNamespace(input_tokens=7)

    class _OpenAI:
        def __init__(self, **kwargs):
            self.responses = SimpleNamespace(input_tokens=_Count())

    openai.OpenAI = _OpenAI
    monkeypatch.setitem(sys.modules, "openai", openai)

    google = ModuleType("google")
    genai = ModuleType("google.genai")
    types = ModuleType("google.genai.types")

    class _Decl:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    class _Tool:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    class _Cfg:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    class _Models:
        def count_tokens(self, **kwargs):
            if kwargs.get("config") is not None and kwargs["model"] == "retry":
                raise RuntimeError("schema")
            if kwargs["model"] == "both":
                raise RuntimeError("nope")
            return SimpleNamespace(total_tokens=5)

    class _GClient:
        def __init__(self, api_key):
            self.models = _Models()

    types.FunctionDeclaration = _Decl
    types.Tool = _Tool
    types.CountTokensConfig = _Cfg
    genai.Client = _GClient
    genai.types = types
    google.genai = genai
    monkeypatch.setitem(sys.modules, "google", google)
    monkeypatch.setitem(sys.modules, "google.genai", genai)
    monkeypatch.setitem(sys.modules, "google.genai.types", types)

    tools = ['{"name": "fold", "input_schema": {"type": "object", "$schema": "draft"}}']
    parts = ["system"]
    assert pc.count_anthropic_input_tokens(model="claude", api_key="sk", system_parts=parts, tool_texts=tools) == 11
    assert pc.count_anthropic_input_tokens(model="boom", api_key="sk", system_parts=[], tool_texts=[]) is None
    assert pc.count_openai_input_tokens(
        model="gpt",
        api_key="sk",
        system_parts=parts,
        tool_texts=tools,
        base_url="https://api.openai.com/v1",
    ) == 7
    assert pc.count_openai_input_tokens(model="boom", api_key="sk", system_parts=[], tool_texts=[]) is None
    assert pc.count_google_input_tokens(model="gemini", api_key="sk", system_parts=parts, tool_texts=tools) == 5
    assert pc.count_google_input_tokens(model="retry", api_key="sk", system_parts=parts, tool_texts=tools) == 5
    assert pc.count_google_input_tokens(model="both", api_key="sk", system_parts=parts, tool_texts=[]) is None

    tokens, label = pc.count_provider_input_tokens(
        provider="anthropic", model="claude", api_key="sk", system_parts=parts, tool_texts=[]
    )
    assert tokens == 11 and label.startswith("anthropic:")
    assert pc.count_provider_input_tokens(
        provider="openai", model="boom", api_key="sk", system_parts=[], tool_texts=[]
    ) == (None, None)
    tokens, label = pc.count_provider_input_tokens(
        provider="google", model="gemini", api_key="sk", system_parts=[], tool_texts=[]
    )
    assert tokens == 5 and "google" in label
    assert pc.count_provider_input_tokens(
        provider="other", model="m", api_key="sk", system_parts=[], tool_texts=[]
    ) == (None, None)


def test_count_import_failures(monkeypatch):
    monkeypatch.setitem(sys.modules, "anthropic", None)
    monkeypatch.setitem(sys.modules, "openai", None)
    monkeypatch.setitem(sys.modules, "google", None)
    assert pc.count_anthropic_input_tokens(model="m", api_key="sk", system_parts=[], tool_texts=[]) is None
    assert pc.count_openai_input_tokens(model="m", api_key="sk", system_parts=[], tool_texts=[]) is None
    assert pc.count_google_input_tokens(model="m", api_key="sk", system_parts=[], tool_texts=[]) is None
