"""Knowledge-level middleware and compatible chat-model branches without a live model."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from langchain.agents.middleware.types import ModelRequest
from langchain_core.messages import SystemMessage

from agent.deepagents_runtime.chat_model_compatible import build_compatible_chat_model
from agent.deepagents_runtime.chat_model_openai import STREAM_CHUNK_TIMEOUT_S
from agent.deepagents_runtime.knowledge_level_middleware import (
    KnowledgeLevelMiddleware,
    _drop_system_block,
    _strip_excluded_system_sections,
    _tool_name,
    apply_knowledge_level_to_system_message,
)

_EXCLUDED = frozenset({"write_todos", "task"})


class _Config:
    def __init__(self, values=None, *, base_url="https://example.test/v1", api_key="test-key"):
        self._values = values or {}
        self._base_url = base_url
        self._api_key = api_key

    def get(self, key, default=None):
        return self._values.get(key, default)

    def llm_provider_base_url(self, provider):  # noqa: ARG002
        return self._base_url

    def llm_api_key(self, provider):  # noqa: ARG002
        return self._api_key


def _request(*, tools=None, system_message=None):
    return ModelRequest(
        model=object(),
        messages=[],
        tools=tools if tools is not None else [],
        system_message=system_message,
    )


def test_tool_name_reads_dicts_and_objects():
    assert _tool_name({"name": "read_file"}) == "read_file"
    assert _tool_name({"name": 1}) is None
    assert _tool_name({}) is None
    assert _tool_name(SimpleNamespace(name="task")) == "task"
    assert _tool_name(SimpleNamespace(name=3)) is None
    assert _tool_name(SimpleNamespace()) is None


def test_drop_and_strip_system_sections():
    assert _drop_system_block("", _EXCLUDED) is False
    assert _drop_system_block("## `write_todos`\nuse it", _EXCLUDED) is True
    assert _drop_system_block("## `task`\nspawn", _EXCLUDED) is True
    assert _drop_system_block("## Skills\nkeep", _EXCLUDED) is False
    assert _drop_system_block("## `write_todos`", frozenset({"task"})) is False
    assert _drop_system_block("## `task`", frozenset({"write_todos"})) is False

    assert _strip_excluded_system_sections("", _EXCLUDED) == ""
    assert _strip_excluded_system_sections("keep", frozenset()) == "keep"

    both = (
        "intro\n"
        "## `write_todos`\n"
        "todo body\n"
        "## `task`\n"
        "task body\n"
        "## Keep\n"
        "kept\n"
    )
    stripped = _strip_excluded_system_sections(both, _EXCLUDED)
    assert "intro" in stripped
    assert "## Keep" in stripped
    assert "kept" in stripped
    assert "write_todos" not in stripped
    assert "`task`" not in stripped

    todos_only = _strip_excluded_system_sections(both, frozenset({"write_todos"}))
    assert "write_todos" not in todos_only
    assert "## `task`" in todos_only

    task_only = _strip_excluded_system_sections(both, frozenset({"task"}))
    assert "## `write_todos`" in task_only
    assert "## `task`" not in task_only

    untouched = _strip_excluded_system_sections(
        "## Other\nbody\n",
        frozenset({"execute"}),
    )
    assert untouched == "## Other\nbody"


def test_apply_knowledge_level_keeps_and_drops_blocks():
    assert apply_knowledge_level_to_system_message(None, _EXCLUDED) is None
    original = SystemMessage(content="stay")
    assert apply_knowledge_level_to_system_message(original, frozenset()) is original

    unchanged_blocks = SystemMessage(
        content=[
            "plain",
            {"type": "text", "text": ""},
            {"type": "text"},
            {"type": "text", "text": "hello"},
        ]
    )
    assert (
        apply_knowledge_level_to_system_message(unchanged_blocks, _EXCLUDED)
        is unchanged_blocks
    )

    mixed = SystemMessage(
        content=[
            {"type": "text", "text": "stay"},
            {"type": "text", "text": "## `write_todos`\n\ngo"},
            "raw",
            {"type": "text", "text": "## `task`\n\nspawn"},
        ]
    )
    filtered = apply_knowledge_level_to_system_message(mixed, _EXCLUDED)
    assert filtered is not None
    assert filtered is not mixed
    assert filtered.content == [
        {"type": "text", "text": "stay"},
        "raw",
    ]

    same_text = SystemMessage(content="no headers here")
    assert apply_knowledge_level_to_system_message(same_text, _EXCLUDED) is same_text

    blank = SystemMessage(content="")
    assert apply_knowledge_level_to_system_message(blank, _EXCLUDED) is blank

    prose = SystemMessage(
        content="intro\n## `write_todos`\nbody\n## After\nkeep\n"
    )
    rewritten = apply_knowledge_level_to_system_message(prose, frozenset({"write_todos"}))
    assert rewritten is not None
    assert rewritten is not prose
    assert "write_todos" not in rewritten.content
    assert "## After" in rewritten.content
    assert "keep" in rewritten.content

    other = SystemMessage.model_construct(content=123)
    assert apply_knowledge_level_to_system_message(other, _EXCLUDED) is other


def test_middleware_filters_request_sync_and_async():
    passthrough = KnowledgeLevelMiddleware(excluded=frozenset())
    original = _request(tools=[{"name": "task"}])

    def identity(request):
        return request

    assert passthrough.wrap_model_call(original, identity) is original

    keep = SimpleNamespace(name="read_file")
    drop_obj = SimpleNamespace(name="write_todos")
    nameless = SimpleNamespace()
    bad_name = SimpleNamespace(name=3)
    tools = [
        {"name": "task"},
        {"name": 1},
        {},
        keep,
        drop_obj,
        nameless,
        bad_name,
    ]
    system = SystemMessage(
        content=[
            {"type": "text", "text": "stay"},
            {"type": "text", "text": "## `task`\n\nspawn"},
            "raw",
        ]
    )
    middleware = KnowledgeLevelMiddleware(excluded=_EXCLUDED)
    request = _request(tools=tools, system_message=system)
    seen = {}

    def handler(filtered):
        seen["request"] = filtered
        return "ok"

    assert middleware.wrap_model_call(request, handler) == "ok"
    filtered = seen["request"]
    assert filtered is not request
    assert filtered.tools == [{"name": 1}, {}, keep, nameless, bad_name]
    assert filtered.system_message.content == [
        {"type": "text", "text": "stay"},
        "raw",
    ]

    no_system = _request(tools=[{"name": "task"}, keep], system_message=None)

    async def async_handler(filtered_request):
        return filtered_request

    result = asyncio.run(middleware.awrap_model_call(no_system, async_handler))
    assert result.tools == [keep]
    assert result.system_message is None

    prose = _request(
        tools=[drop_obj, keep],
        system_message=SystemMessage(content="## `write_todos`\nbody\n## Stay\nok\n"),
    )
    rewritten = asyncio.run(middleware.awrap_model_call(prose, async_handler))
    assert rewritten.tools == [keep]
    assert "write_todos" not in rewritten.system_message.content
    assert "## Stay" in rewritten.system_message.content


def _capture_init(monkeypatch):
    captured: dict = {}

    def fake_init(model, **kwargs):
        captured["model"] = model
        captured["kwargs"] = kwargs
        return {"built": model}

    monkeypatch.setattr("langchain.chat_models.init_chat_model", fake_init)
    return captured


def _reasoning_config(model, **extra):
    values = {
        "llm.model": model,
        "llm.model_reasoning": {},
        "llm.reasoning_effort": "high",
        "llm.reasoning_fast": False,
    }
    values.update(extra)
    return values


def test_compatible_chat_model_rejects_missing_base_url(monkeypatch):
    captured = _capture_init(monkeypatch)
    with pytest.raises(ValueError, match="not-a-provider"):
        build_compatible_chat_model(
            _Config(_reasoning_config("grok-4.5"), base_url=""),
            "not-a-provider",
            temperature=0.2,
        )
    assert captured == {}


def test_opencode_anthropic_effort_omits_temperature(monkeypatch):
    captured = _capture_init(monkeypatch)
    built = build_compatible_chat_model(
        _Config(
            _reasoning_config("claude-sonnet-5"),
            base_url="https://opencode.ai/zen/v1",
            api_key="zen-key",
        ),
        "opencode",
        temperature=0.2,
    )
    assert built == {"built": "anthropic:claude-sonnet-5"}
    assert captured["kwargs"] == {
        "api_key": "zen-key",
        "base_url": "https://opencode.ai/zen",
        "effort": "high",
    }


def test_opencode_anthropic_without_key_or_effort_keeps_temperature(monkeypatch):
    captured = _capture_init(monkeypatch)
    build_compatible_chat_model(
        _Config(
            _reasoning_config("qwen3.7-plus"),
            base_url="https://opencode.ai/zen/v1",
            api_key="",
        ),
        "opencode",
        temperature=0.4,
    )
    assert captured["model"] == "anthropic:qwen3.7-plus"
    assert captured["kwargs"] == {
        "temperature": 0.4,
        "base_url": "https://opencode.ai/zen",
    }


def test_opencode_gpt_uses_responses_api_and_reasoning(monkeypatch):
    captured = _capture_init(monkeypatch)
    build_compatible_chat_model(
        _Config(
            _reasoning_config("gpt-5.4"),
            base_url="https://opencode.ai/zen/v1",
            api_key="zen-key",
        ),
        "opencode",
        temperature=0.2,
    )
    assert captured["model"] == "openai:gpt-5.4"
    assert captured["kwargs"] == {
        "api_key": "zen-key",
        "base_url": "https://opencode.ai/zen/v1",
        "use_responses_api": True,
        "stream_chunk_timeout": STREAM_CHUNK_TIMEOUT_S,
        "reasoning_effort": "high",
    }


def test_xai_sets_reasoning_effort(monkeypatch):
    captured = _capture_init(monkeypatch)
    build_compatible_chat_model(
        _Config(
            _reasoning_config("grok-4.5"),
            base_url="https://api.x.ai/v1",
            api_key="xai-key",
        ),
        "xai",
        temperature=0.1,
    )
    assert captured["model"] == "openai:grok-4.5"
    assert captured["kwargs"] == {
        "temperature": 0.1,
        "api_key": "xai-key",
        "base_url": "https://api.x.ai/v1",
        "use_responses_api": False,
        "stream_chunk_timeout": STREAM_CHUNK_TIMEOUT_S,
        "reasoning_effort": "high",
    }


def test_non_reasoning_provider_uses_default_model_without_key(monkeypatch):
    captured = _capture_init(monkeypatch)
    build_compatible_chat_model(
        _Config(
            _reasoning_config(None),
            base_url="https://integrate.api.nvidia.com/v1",
            api_key=None,
        ),
        "nvidia",
        temperature=0.3,
    )
    assert captured["model"] == "openai:nvidia/nemotron-3-ultra-550b-a55b"
    assert captured["kwargs"] == {
        "temperature": 0.3,
        "base_url": "https://integrate.api.nvidia.com/v1",
        "use_responses_api": False,
        "stream_chunk_timeout": STREAM_CHUNK_TIMEOUT_S,
    }


def test_unknown_provider_with_base_url_builds_openai_model(monkeypatch):
    captured = _capture_init(monkeypatch)
    build_compatible_chat_model(
        _Config(
            {"llm.model": ""},
            base_url="https://custom.example/v1",
            api_key=None,
        ),
        "custom",
        temperature=0.5,
    )
    assert captured["model"] == "openai:"
    assert "reasoning_effort" not in captured["kwargs"]
    assert captured["kwargs"]["use_responses_api"] is False
    assert captured["kwargs"]["temperature"] == 0.5


def test_moonshot_reasoning_uses_generic_effort(monkeypatch):
    captured = _capture_init(monkeypatch)
    build_compatible_chat_model(
        _Config(
            _reasoning_config("kimi-k2.5"),
            base_url="https://api.moonshot.ai/v1",
            api_key="moon-key",
        ),
        "moonshot",
        temperature=0.0,
    )
    assert captured["model"] == "openai:kimi-k2.5"
    assert captured["kwargs"]["reasoning_effort"] == "high"
    assert captured["kwargs"]["temperature"] == 0.0
    assert captured["kwargs"]["use_responses_api"] is False
