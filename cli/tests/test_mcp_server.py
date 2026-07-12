"""Tests for agent.mcp_server tool formatting and shared sandbox handlers."""

import asyncio
import sys
from types import ModuleType, SimpleNamespace
from dataclasses import dataclass
from unittest.mock import MagicMock, patch

from agent.mcp_server import (
    _format_tool_result,
    _make_tool_handler,
    _params_to_json_schema,
)


class TestFormatToolResult:
    def test_non_dict_truncates(self):
        long_text = "x" * 9000
        assert len(_format_tool_result(long_text)) == 8000

    def test_dict_with_summary_and_compact_keys(self):
        result = {
            "summary": "Found 3 hits",
            "top_hits": [{"a": 1}, {"b": 2}],
            "gene": "TP53",
        }
        text = _format_tool_result(result)
        assert "Found 3 hits" in text
        assert "top_hits: list with 2 entries" in text
        assert "gene: TP53" in text

    def test_long_field_value_truncated(self):
        result = {"summary": "ok", "data": "z" * 2000}
        text = _format_tool_result(result)
        assert "chars total" in text


class TestParamsToJsonSchema:
    def test_empty_parameters(self):
        schema = _params_to_json_schema({})
        assert schema == {"type": "object", "properties": {}}

    def test_maps_descriptions(self):
        schema = _params_to_json_schema({"gene": "Gene symbol", "limit": "Max rows"})
        assert schema["properties"]["gene"]["description"] == "Gene symbol"
        assert schema["properties"]["limit"]["type"] == "string"


@dataclass
class _FakeTool:
    name: str = "target.druggability"
    description: str = "Score druggability"
    parameters: dict = None
    category: str = "target"

    def __post_init__(self):
        if self.parameters is None:
            self.parameters = {"gene": "Gene symbol"}

    def run(self, **kwargs):
        return {"summary": f"Druggability for {kwargs.get('gene')}"}


class TestMakeToolHandler:
    def test_coerces_numeric_and_bool_strings(self):
        session = MagicMock()
        tool = _FakeTool()
        calls = []

        def _record(**kwargs):
            calls.append(kwargs)
            return {"summary": "ok"}

        tool.run = _record
        handler = _make_tool_handler(tool, session)
        result = asyncio.run(handler({
            "gene": "TP53",
            "limit": "10",
            "threshold": "0.25",
            "active": "true",
        }))
        assert result["content"][0]["text"] == "ok"
        assert calls[0]["limit"] == 10
        assert calls[0]["threshold"] == 0.25
        assert calls[0]["active"] is True

    def test_tool_exception_returns_is_error(self):
        session = MagicMock()
        tool = _FakeTool()

        def _boom(**kwargs):
            raise RuntimeError("tool failed")

        tool.run = _boom
        handler = _make_tool_handler(tool, session)
        result = asyncio.run(handler({"gene": "TP53"}))
        assert result["is_error"] is True
        assert "tool failed" in result["content"][0]["text"]


class TestRunPythonHandler:
    def test_empty_code_returns_error(self):
        from agent.mcp_server import _make_run_python_handler

        session = MagicMock()
        session.config = MagicMock()
        session.config.get.side_effect = lambda key, default=None: {
            "sandbox.timeout": 30,
            "sandbox.max_retries": 1,
        }.get(key, default)

        with patch("agent.sandbox.Sandbox") as mock_sandbox_cls:
            mock_sandbox_cls.return_value.load_datasets.return_value = None
            handler, _sandbox = _make_run_python_handler(session)

        result = asyncio.run(handler({"code": "   "}))
        assert result["is_error"] is True
        assert "no code" in result["content"][0]["text"].lower()

    def test_successful_execution_with_trace_buffer(self):
        from agent.mcp_server import _make_run_python_handler

        session = MagicMock()
        session.config = MagicMock()
        session.config.get.side_effect = lambda key, default=None: {
            "sandbox.timeout": 30,
            "sandbox.max_retries": 1,
        }.get(key, default)

        buffer = []
        mock_sandbox = MagicMock()
        mock_sandbox.execute.return_value = {
            "stdout": "hello world",
            "plots": ["/tmp/plot.png"],
            "exports": [],
            "error": None,
        }
        mock_sandbox.get_variable.return_value = {
            "summary": "done",
            "answer": "42",
        }

        with patch("agent.sandbox.Sandbox", return_value=mock_sandbox):
            handler, sandbox = _make_run_python_handler(session, buffer)

        result = asyncio.run(handler({"code": "print('hello world')"}))
        assert result["is_error"] is False
        text = result["content"][0]["text"]
        assert "hello world" in text
        assert "Result summary: done" in text
        assert len(buffer) == 1
        assert buffer[0]["tool"] == "run_python"
        assert sandbox is mock_sandbox

    def test_execution_error_exports_and_extra_read_dirs(self, tmp_path):
        from agent.mcp_server import _make_run_python_handler

        readable = tmp_path / "readable"
        readable.mkdir()
        missing = tmp_path / "missing"
        session = MagicMock()
        session.config.get.side_effect = lambda key, default=None: {
            "sandbox.timeout": "12",
            "sandbox.output_dir": str(tmp_path / "output"),
            "sandbox.max_retries": "3",
            "sandbox.extra_read_dirs": f" {readable}, {missing}, ",
        }.get(key, default)
        sandbox = MagicMock()
        sandbox.execute.return_value = {
            "stdout": "",
            "error": "division failed",
            "plots": ["/tmp/plot.png"],
            "exports": ["/tmp/table.csv"],
        }
        sandbox.get_variable.return_value = {
            "summary": "partial",
            "answer": "retry with filtered rows",
        }
        tools_namespace = object()

        with patch("agent.sandbox.Sandbox", return_value=sandbox) as sandbox_cls:
            handler, _ = _make_run_python_handler(
                session, tools_namespace=tools_namespace
            )

        result = asyncio.run(handler({"code": "1 / 0"}))

        assert result["is_error"] is True
        text = result["content"][0]["text"]
        assert "division failed" in text
        assert "Plots saved" in text
        assert "Exports saved" in text
        assert "Result answer: retry with filtered rows" in text
        assert sandbox_cls.call_args.kwargs["extra_read_dirs"] == [readable]
        sandbox.inject_tools.assert_called_once_with(tools_namespace)


class TestRunRHandler:
    def test_empty_code_returns_error(self):
        from agent.mcp_server import _make_run_r_handler

        result = asyncio.run(_make_run_r_handler()({"code": "  "}))

        assert result["is_error"] is True
        assert "no R code" in result["content"][0]["text"]

    def test_missing_rpy2_returns_traced_error(self):
        from agent.mcp_server import _make_run_r_handler

        trace = []
        with patch.dict(sys.modules, {"rpy2": None, "rpy2.robjects": None}):
            result = asyncio.run(_make_run_r_handler(trace)({"code": "1 + 1"}))

        assert result["is_error"] is True
        assert result["content"][0]["text"].startswith("R Error:")
        assert trace[0]["tool"] == "run_r"
        assert trace[0]["error"].startswith("R Error:")

    def test_successful_scalar_execution(self):
        from agent.mcp_server import _make_run_r_handler

        robjects = ModuleType("rpy2.robjects")
        calls = []

        def run(code):
            calls.append(code)
            return ["captured output"] if code.startswith("paste(") else [42]

        robjects.r = run
        robjects.NULL = object()
        robjects.numpy2ri = SimpleNamespace(activate=MagicMock(), deactivate=MagicMock())
        robjects.pandas2ri = SimpleNamespace(activate=MagicMock(), deactivate=MagicMock())
        rpy2 = ModuleType("rpy2")
        rpy2.robjects = robjects
        trace = []

        with patch.dict(sys.modules, {"rpy2": rpy2, "rpy2.robjects": robjects}):
            result = asyncio.run(_make_run_r_handler(trace)({"code": "21 * 2"}))

        text = result["content"][0]["text"]
        assert result["is_error"] is False
        assert "captured output" in text
        assert "Return value: 42.0" in text
        assert len(calls) == 2
        robjects.numpy2ri.deactivate.assert_called_once()
        robjects.pandas2ri.deactivate.assert_called_once()
        assert trace[0]["stdout"] == text

    def test_vector_and_large_return_values(self):
        from agent.mcp_server import _make_run_r_handler

        robjects = ModuleType("rpy2.robjects")
        returns = iter([["a", "b"], list(range(51))])

        def run(code):
            return [] if code.startswith("paste(") else next(returns)

        robjects.r = run
        robjects.NULL = object()
        robjects.numpy2ri = SimpleNamespace(activate=MagicMock(), deactivate=MagicMock())
        robjects.pandas2ri = SimpleNamespace(activate=MagicMock(), deactivate=MagicMock())
        rpy2 = ModuleType("rpy2")
        rpy2.robjects = robjects

        with patch.dict(sys.modules, {"rpy2": rpy2, "rpy2.robjects": robjects}):
            vector = asyncio.run(_make_run_r_handler()({"code": "c('a', 'b')"}))
            large = asyncio.run(_make_run_r_handler()({"code": "1:51"}))

        assert "Return value: [a, b]" in vector["content"][0]["text"]
        assert "Return value: [0, 1, 2" in large["content"][0]["text"]

    def test_capture_fallback_and_return_rendering_fallbacks(self):
        from agent.mcp_server import _make_run_r_handler

        class BadLength:
            def __len__(self):
                raise RuntimeError("length unavailable")

            def __str__(self):
                return "custom R result"

        robjects = ModuleType("rpy2.robjects")
        calls = 0

        def run(code):
            nonlocal calls
            calls += 1
            if calls == 1:
                raise RuntimeError("capture failed")
            if calls == 2:
                return ["fallback output"]
            return BadLength()

        robjects.r = run
        robjects.NULL = object()
        robjects.numpy2ri = SimpleNamespace(activate=MagicMock(), deactivate=MagicMock())
        robjects.pandas2ri = SimpleNamespace(activate=MagicMock(), deactivate=MagicMock())
        rpy2 = ModuleType("rpy2")
        rpy2.robjects = robjects

        with patch.dict(sys.modules, {"rpy2": rpy2, "rpy2.robjects": robjects}):
            result = asyncio.run(_make_run_r_handler()({"code": "complex_result()"}))

        text = result["content"][0]["text"]
        assert "fallback output" in text
        assert "Return value: custom R result" in text

    def test_last_expression_error_keeps_captured_output(self):
        from agent.mcp_server import _make_run_r_handler

        robjects = ModuleType("rpy2.robjects")
        robjects.r = MagicMock(side_effect=[["printed first"], RuntimeError("second run failed")])
        robjects.NULL = object()
        robjects.numpy2ri = SimpleNamespace(activate=MagicMock(), deactivate=MagicMock())
        robjects.pandas2ri = SimpleNamespace(activate=MagicMock(), deactivate=MagicMock())
        rpy2 = ModuleType("rpy2")
        rpy2.robjects = robjects

        with patch.dict(sys.modules, {"rpy2": rpy2, "rpy2.robjects": robjects}):
            result = asyncio.run(_make_run_r_handler()({"code": "print('first')"}))

        assert result["is_error"] is False
        assert result["content"][0]["text"] == "printed first"

    def test_capture_and_direct_execution_errors(self):
        from agent.mcp_server import _make_run_r_handler

        robjects = ModuleType("rpy2.robjects")
        robjects.r = MagicMock(side_effect=RuntimeError("bad R expression"))
        robjects.NULL = object()
        robjects.numpy2ri = SimpleNamespace(activate=MagicMock(), deactivate=MagicMock())
        robjects.pandas2ri = SimpleNamespace(activate=MagicMock(), deactivate=MagicMock())
        rpy2 = ModuleType("rpy2")
        rpy2.robjects = robjects

        with patch.dict(sys.modules, {"rpy2": rpy2, "rpy2.robjects": robjects}):
            result = asyncio.run(_make_run_r_handler()({"code": "broken("}))

        assert result["is_error"] is True
        assert "bad R expression" in result["content"][0]["text"]
