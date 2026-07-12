"""Unit tests for the deepagents (LangGraph) runtime backend.

Covers the model factory (``build_chat_model`` provider routing), the pure
helpers, the registry -> LangChain tool adapter (native + PTC), and
``process_events`` translating a synthetic ``astream_events`` stream into the
trace/result contract.
"""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from agent import deepagents_runtime as dr


# ---------------------------------------------------------------------------
# Fakes for the astream_events stream
# ---------------------------------------------------------------------------

class _Chunk:
    def __init__(self, content):
        self.content = content


class _Msg:
    def __init__(self, content="", usage_metadata=None):
        self.content = content
        if usage_metadata is not None:
            self.usage_metadata = usage_metadata


class _ToolOut:
    def __init__(self, content, status="success"):
        self.content = content
        self.status = status


async def _aiter(events):
    for event in events:
        yield event


def _run(coro):
    return asyncio.run(coro)


# ---------------------------------------------------------------------------
# build_chat_model
# ---------------------------------------------------------------------------

def _stub_config(provider="anthropic", model=None, *, api_key=None, base_url=None, temperature=0.1):
    data = {
        "llm.provider": provider,
        "llm.model": model,
        "llm.temperature": temperature,
    }
    return SimpleNamespace(
        get=lambda key, default=None: data.get(key, default),
        llm_api_key=lambda _provider: api_key,
        llm_openai_base_url=lambda: base_url,
        llm_provider_base_url=lambda _provider: None,
    )


class TestBuildChatModel:
    def _patch_init(self, monkeypatch):
        captured = {}

        def fake_init(model_id, **kwargs):
            captured["model_id"] = model_id
            captured["kwargs"] = kwargs
            return SimpleNamespace(model_id=model_id, kwargs=kwargs)

        monkeypatch.setattr("langchain.chat_models.init_chat_model", fake_init)
        return captured

    def test_anthropic_defaults_and_api_key(self, monkeypatch):
        captured = self._patch_init(monkeypatch)
        dr.build_chat_model(_stub_config("anthropic", api_key="sk-ant"))
        assert captured["model_id"] == "anthropic:claude-sonnet-4-5-20250929"
        assert captured["kwargs"]["temperature"] == 0.1
        assert captured["kwargs"]["api_key"] == "sk-ant"

    def test_anthropic_explicit_model_no_key(self, monkeypatch):
        captured = self._patch_init(monkeypatch)
        dr.build_chat_model(_stub_config("anthropic", model="claude-x"))
        assert captured["model_id"] == "anthropic:claude-x"
        assert "api_key" not in captured["kwargs"]

    def test_openai_with_base_url_and_temperature(self, monkeypatch):
        captured = self._patch_init(monkeypatch)
        dr.build_chat_model(
            _stub_config("openai", model="gpt-4o", api_key="k", base_url="http://localhost:11434/v1")
        )
        assert captured["model_id"] == "openai:gpt-4o"
        assert captured["kwargs"]["temperature"] == 0.1
        assert captured["kwargs"]["api_key"] == "k"
        assert captured["kwargs"]["base_url"] == "http://localhost:11434/v1"
        assert captured["kwargs"]["use_responses_api"] is False

    def test_openai_gpt5_omits_temperature(self, monkeypatch):
        captured = self._patch_init(monkeypatch)
        dr.build_chat_model(_stub_config("openai", model="gpt-5-mini"))
        assert captured["model_id"] == "openai:gpt-5-mini"
        assert "temperature" not in captured["kwargs"]
        assert captured["kwargs"]["use_responses_api"] is False

    def test_openai_codex_uses_responses_api_on_cloud(self, monkeypatch):
        captured = self._patch_init(monkeypatch)
        dr.build_chat_model(_stub_config("openai", model="gpt-5.3-codex", api_key="k"))
        assert captured["model_id"] == "openai:gpt-5.3-codex"
        assert captured["kwargs"]["use_responses_api"] is True

    def test_openai_codex_keeps_chat_completions_on_local(self, monkeypatch):
        captured = self._patch_init(monkeypatch)
        dr.build_chat_model(
            _stub_config(
                "openai",
                model="gpt-5.3-codex",
                api_key="k",
                base_url="http://localhost:11434/v1",
            )
        )
        assert captured["kwargs"]["use_responses_api"] is False

    def test_unsupported_provider_raises(self, monkeypatch):
        self._patch_init(monkeypatch)
        with pytest.raises(ValueError, match="does not support"):
            dr.build_chat_model(_stub_config("cohere"))


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------

class TestHelpers:
    def test_sanitize_tool_name(self):
        assert dr._sanitize_tool_name("target.neo!") == "target_neo_"
        assert dr._sanitize_tool_name("") == "tool"
        assert dr._sanitize_tool_name("ok-name_1") == "ok-name_1"

    def test_text_from_content_variants(self):
        assert dr._text_from_content("hello") == "hello"
        assert dr._text_from_content(
            [{"type": "text", "text": "a"}, {"type": "thinking"}, "b"]
        ) == "ab"
        assert dr._text_from_content(42) == ""

    def test_tool_output_text_variants(self):
        assert dr._tool_output_text(_ToolOut("plain")) == "plain"
        assert dr._tool_output_text(
            _ToolOut([{"type": "text", "text": "x"}, "y"])
        ) == "x\ny"
        assert dr._tool_output_text(None) == ""
        assert dr._tool_output_text(_ToolOut(None)) == ""
        assert dr._tool_output_text(123) == "123"

    def test_usage_from_message(self):
        msg = _Msg(usage_metadata={
            "input_tokens": 10,
            "output_tokens": 3,
            "input_token_details": {"cache_read": 7, "cache_creation": 2},
        })
        usage = dr._usage_from_message(msg)
        assert usage == {
            "input_tokens": 10,
            "output_tokens": 3,
            "cache_creation_input_tokens": 2,
            "cache_read_input_tokens": 7,
        }
        assert dr._usage_from_message(_Msg("no usage")) is None

    def test_args_schema_for_filters_and_required_code(self):
        model = dr._args_schema_for(
            "demo",
            {"gene": "the gene", "bad-name": "skip", "_hidden": "skip", "code": "skip"},
            required_code=True,
        )
        fields = model.model_fields
        assert "code" in fields
        assert "gene" in fields
        assert "bad-name" not in fields
        assert "_hidden" not in fields

    def test_cap_tools_for_openai_keeps_pinned(self):
        tools = [SimpleNamespace(name=n) for n in ("a", "b", "c", "d", "run_python")]
        capped = dr._cap_tools_for_openai(tools, max_total=3)
        names = {t.name for t in capped}
        assert len(capped) == 3
        assert "run_python" in names

    def test_cap_tools_for_openai_under_budget_is_copy(self):
        tools = [SimpleNamespace(name="a"), SimpleNamespace(name="b")]
        capped = dr._cap_tools_for_openai(tools, max_total=10)
        assert capped == tools
        assert capped is not tools


class TestSkillSourceDirs:
    def test_filters_to_existing_dirs(self, tmp_path, monkeypatch):
        existing = tmp_path / "bundled"
        existing.mkdir()
        missing = tmp_path / "nope"
        monkeypatch.setattr("agent.skills.BUNDLED_SKILLS_DIR", str(existing), raising=False)
        monkeypatch.setattr("agent.skills.NPX_SKILLS_DIR", str(missing), raising=False)
        monkeypatch.setattr("agent.skills.GLOBAL_SKILLS_DIR", None, raising=False)
        sources = dr.skill_source_dirs()
        assert str(existing) in sources
        assert str(missing) not in sources


class TestLcToolAdapter:
    def test_coroutine_strips_none_and_extracts_text(self):
        async def handler(args):
            assert "y" not in args
            assert args["x"] == "1"
            return {"content": [{"type": "text", "text": "ok"}]}

        tool = dr._make_lc_tool(
            name="t",
            description="d",
            args_schema=dr._args_schema_for("t", {"x": "x", "y": "y"}),
            handler=handler,
        )
        out = _run(tool.coroutine(x="1", y=None))
        assert out == "ok"

    def test_coroutine_empty_output_fallback(self):
        async def handler(args):
            return {"content": []}

        tool = dr._make_lc_tool(
            name="t",
            description="",
            args_schema=dr._args_schema_for("t", None),
            handler=handler,
        )
        assert _run(tool.coroutine()) == "(no output)"

    def test_sync_func_unsupported(self):
        async def handler(args):
            return {"content": []}

        tool = dr._make_lc_tool(
            name="t",
            description="d",
            args_schema=dr._args_schema_for("t", None),
            handler=handler,
        )
        with pytest.raises(NotImplementedError):
            tool.func()

    def test_search_tools_tool_invokes_search(self, monkeypatch):
        captured = {}

        def fake_search(query, **kwargs):
            captured["query"] = query
            captured["kwargs"] = kwargs
            return "SIGNATURES"

        monkeypatch.setattr("agent.ptc_tools.search_tools_text", fake_search)
        tool = dr._make_search_tools_tool({"genomics"}, {"x.y"})
        assert tool.name == "search_tools"
        out = _run(tool.coroutine("kinase", category="target", limit=5))
        assert out == "SIGNATURES"
        assert captured["query"] == "kinase"
        assert captured["kwargs"]["limit"] == 5
        assert captured["kwargs"]["exclude_categories"] == {"genomics"}


# ---------------------------------------------------------------------------
# create_ct_langchain_tools
# ---------------------------------------------------------------------------

def _tool_session():
    return SimpleNamespace(config=SimpleNamespace(get=lambda key, default=None: default))


class TestCreateLangchainTools:
    def test_native_mode_builds_tools(self):
        tools, sandbox, buf, dmap = dr.create_ct_langchain_tools(
            _tool_session(),
            include_run_python=False,
            provider="anthropic",
            tool_mode="native",
        )
        assert sandbox is None
        assert buf == []
        assert len(tools) > 50
        # display map round-trips a sanitized name to a dotted registry name.
        assert any("." in original for original in dmap.values())
        names = {getattr(t, "name", "") for t in tools}
        assert all(name for name in names)

    def test_openai_native_mode_is_capped(self):
        tools, _sandbox, _buf, _dmap = dr.create_ct_langchain_tools(
            _tool_session(),
            include_run_python=False,
            provider="openai",
            tool_mode="native",
        )
        assert len(tools) <= dr.OPENAI_TOOL_BUDGET

    def test_ptc_mode_exposes_search_and_shell(self):
        tools, _sandbox, _buf, dmap = dr.create_ct_langchain_tools(
            _tool_session(),
            include_run_python=False,
            tool_mode="ptc",
        )
        names = {getattr(t, "name", "") for t in tools}
        assert "search_tools" in names
        assert "search_tools" in dmap
        # PTC exposes only a handful of schemas (search_tools + shell), not the
        # full domain fan-out.
        assert len(tools) <= 5

    def test_include_run_python_adds_sandbox_tool(self, monkeypatch):
        fake_sandbox = SimpleNamespace(name="sbox")

        async def fake_handler(args):
            return {"content": []}

        monkeypatch.setattr(
            "agent.mcp_server._make_run_python_handler",
            lambda *a, **k: (fake_handler, fake_sandbox),
        )
        tools, sandbox, _buf, dmap = dr.create_ct_langchain_tools(
            _tool_session(),
            include_run_python=True,
            tool_mode="native",
        )
        names = {getattr(t, "name", "") for t in tools}
        assert "run_python" in names
        assert sandbox is fake_sandbox
        assert dmap["run_python"] == "run_python"

    def test_ptc_include_run_python_binds_tools_namespace(self, monkeypatch):
        captured = {}
        fake_sandbox = SimpleNamespace(name="sbox")

        async def fake_handler(args):
            return {"content": []}

        def fake_make(session, code_trace_buffer, tools_namespace=None):
            captured["namespace"] = tools_namespace
            return fake_handler, fake_sandbox

        monkeypatch.setattr("agent.mcp_server._make_run_python_handler", fake_make)
        tools, sandbox, _buf, _dmap = dr.create_ct_langchain_tools(
            _tool_session(),
            include_run_python=True,
            tool_mode="ptc",
        )
        names = {getattr(t, "name", "") for t in tools}
        assert "run_python" in names
        assert "search_tools" in names
        # PTC binds the domain-tool namespace into the sandbox.
        assert captured["namespace"] is not None


# ---------------------------------------------------------------------------
# process_events
# ---------------------------------------------------------------------------

class TestProcessEvents:
    def test_headless_capture_text_tool_and_usage(self):
        events = [
            {"event": "on_tool_start", "name": "neo", "run_id": "r1",
             "data": {"input": {"gene": "TP53"}}},
            {"event": "on_tool_end", "name": "neo", "run_id": "r1",
             "data": {"output": _ToolOut("scored 0.9")}},
            {"event": "on_chat_model_end", "data": {"output": _Msg(
                "Final summary",
                {"input_tokens": 100, "output_tokens": 20,
                 "input_token_details": {"cache_read": 10, "cache_creation": 5}},
            )}},
        ]
        trace_events: list[dict] = []
        result = _run(dr.process_events(
            _aiter(events),
            headless=True,
            trace_events=trace_events,
            display_name_map={"neo": "target.neo"},
            allow_live_spinner=False,
            group_tools=False,
        ))
        assert result["full_text"] == ["Final summary"]
        assert result["model_call_count"] == 1
        assert result["tool_calls"][0]["name"] == "target.neo"
        assert result["tool_calls"][0]["result_text"] == "scored 0.9"
        assert result["token_usage"]["input_tokens"] == 100
        assert result["token_usage"]["output_tokens"] == 20
        assert result["token_usage"]["cache_read_input_tokens"] == 10
        assert result["token_usage"]["cache_creation_input_tokens"] == 5
        types = [e["type"] for e in trace_events]
        assert types == ["tool_start", "tool_result", "text"]

    def test_on_activity_receives_progress(self):
        collected: list[tuple] = []

        def on_activity(event=None, **payload):
            collected.append((event, payload))

        events = [
            {"event": "on_chat_model_stream", "data": {"chunk": _Chunk("hi")}},
            {"event": "on_chat_model_end", "data": {"output": _Msg(
                "done", {"input_tokens": 5, "output_tokens": 1},
            )}},
        ]
        _run(dr.process_events(
            _aiter(events),
            headless=True,
            on_activity=on_activity,
            allow_live_spinner=False,
            group_tools=True,
        ))
        names = [c[0] for c in collected]
        assert "stream" in names
        assert "usage" in names

    def test_grouped_tools_trailing_window(self):
        renderer = MagicMock()
        renderer.console = MagicMock()
        events = []
        for i in range(4):
            rid = f"r{i}"
            events.append({"event": "on_tool_start", "name": "neo", "run_id": rid,
                           "data": {"input": {"i": i}}})
            events.append({"event": "on_tool_end", "name": "neo", "run_id": rid,
                           "data": {"output": _ToolOut(f"out{i}")}})
        events.append({"event": "on_chat_model_end",
                       "data": {"output": _Msg("wrap up")}})
        result = _run(dr.process_events(
            _aiter(events),
            trace_renderer=renderer,
            headless=False,
            display_name_map={"neo": "target.neo"},
            allow_live_spinner=False,
            group_tools=True,
            tool_detail_limit=2,
        ))
        assert len(result["tool_calls"]) == 4
        # The two most recent calls render in full; older ones collapse to a
        # compact console line.
        assert renderer.render_tool_complete.call_count == 2
        assert renderer.console.print.call_count >= 2

    def test_error_tool_renders_error_and_marks_trace(self):
        renderer = MagicMock()
        events = [
            {"event": "on_tool_start", "name": "boom", "run_id": "r1",
             "data": {"input": {}}},
            {"event": "on_tool_end", "name": "boom", "run_id": "r1",
             "data": {"output": _ToolOut("kaboom", status="error")}},
        ]
        trace_events: list[dict] = []
        _run(dr.process_events(
            _aiter(events),
            trace_renderer=renderer,
            headless=False,
            trace_events=trace_events,
            display_name_map={"boom": "target.boom"},
            allow_live_spinner=False,
            group_tools=False,
        ))
        renderer.render_tool_error.assert_called_once()
        result_evt = next(e for e in trace_events if e["type"] == "tool_result")
        assert result_evt["is_error"] is True

    def test_write_todos_render_checklist(self):
        renderer = MagicMock()
        todos = [{"content": "step 1", "status": "pending"}]
        events = [
            {"event": "on_tool_start", "name": "write_todos", "run_id": "r1",
             "data": {"input": {"todos": todos}}},
            {"event": "on_tool_end", "name": "write_todos", "run_id": "r1",
             "data": {"output": _ToolOut("ok")}},
        ]
        _run(dr.process_events(
            _aiter(events),
            trace_renderer=renderer,
            headless=False,
            display_name_map={"write_todos": "write_todos"},
            allow_live_spinner=False,
            group_tools=True,
        ))
        renderer.render_todos.assert_called_once_with(todos)

    def test_run_python_code_buffer_maps_into_trace(self):
        code_buffer = [{
            "stdout": "computed",
            "error": None,
            "code": "print('hi')",
            "plots": ["plot.png"],
            "exports": [],
        }]
        events = [
            {"event": "on_tool_start", "name": "run_python", "run_id": "r1",
             "data": {"input": {"code": "print('hi')"}}},
            {"event": "on_tool_end", "name": "run_python", "run_id": "r1",
             "data": {"output": _ToolOut("truncated")}},
        ]
        trace_events: list[dict] = []
        _run(dr.process_events(
            _aiter(events),
            headless=True,
            trace_events=trace_events,
            display_name_map={"run_python": "run_python"},
            code_trace_buffer=code_buffer,
            allow_live_spinner=False,
            group_tools=False,
        ))
        result_evt = next(e for e in trace_events if e["type"] == "tool_result")
        assert result_evt["code"] == "print('hi')"
        assert result_evt["plots"] == ["plot.png"]
        assert result_evt["result_text"] == "computed"
