"""Tests for tools.code._agentic_code_loop."""

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from models.llm import LLMResponse
from tools.code import _agentic_code_loop


def _tool_use_block(code: str, tool_id: str = "toolu_1"):
    return SimpleNamespace(type="tool_use", id=tool_id, input={"code": code})


@pytest.fixture
def mock_session(tmp_path):
    session = MagicMock()
    session.config.get.side_effect = lambda key, default=None: {
        "sandbox.max_reflect": 2,
    }.get(key, default)
    status = MagicMock()
    status.__enter__ = MagicMock(return_value=status)
    status.__exit__ = MagicMock(return_value=False)
    session.console.status.return_value = status
    return session


class TestAgenticCodeLoop:
    def test_no_tool_calls_returns_error(self, mock_session):
        llm = MagicMock()
        llm.chat.return_value = LLMResponse(content="done", model="test", content_blocks=[])
        sandbox = MagicMock()
        sandbox.get_variable.return_value = None

        result = _agentic_code_loop(
            goal="explore data",
            system_prompt="sys",
            llm=llm,
            sandbox=sandbox,
            session=mock_session,
            max_turns=3,
        )

        assert "no code was executed" in result["summary"]
        assert result["error"] == "LLM did not call run_python tool."
        sandbox.execute.assert_not_called()

    def test_single_tool_call_with_result_dict(self, mock_session):
        llm = MagicMock()
        llm.chat.side_effect = [
            LLMResponse(
                content="",
                model="test",
                content_blocks=[_tool_use_block("result = {'summary': 'computed mean'}")],
            ),
            LLMResponse(content="LGTM", model="test", content_blocks=[]),
        ]
        sandbox = MagicMock()
        sandbox.execute.return_value = {"stdout": "mean=3.0", "error": None, "plots": [], "exports": []}
        sandbox.get_variable.return_value = {"summary": "computed mean", "answer": 3}

        result = _agentic_code_loop(
            goal="compute mean",
            system_prompt="sys",
            llm=llm,
            sandbox=sandbox,
            session=mock_session,
            max_turns=1,
        )

        assert result["summary"] == "computed mean"
        assert "result = {'summary': 'computed mean'}" in result["code"]
        assert result["stdout"] == "mean=3.0"
        sandbox.execute.assert_called_once()

    def test_reflection_applies_fixed_code(self, mock_session):
        mock_session.config.get.side_effect = lambda key, default=None: {
            "sandbox.max_reflect": 1,
        }.get(key, default)
        llm = MagicMock()
        llm.chat.side_effect = [
            LLMResponse(
                content="",
                model="test",
                content_blocks=[_tool_use_block("x = 1")],
            ),
            LLMResponse(
                content="```python\nresult = {'summary': 'fixed'}\n```",
                model="test",
                content_blocks=[],
            ),
        ]
        sandbox = MagicMock()
        sandbox.execute.side_effect = [
            {"stdout": "x=1", "error": None, "plots": [], "exports": []},
            {"stdout": "fixed=ok", "error": None, "plots": ["plot.png"], "exports": ["out.csv"]},
        ]
        sandbox.get_variable.side_effect = [None, {"summary": "fixed", "answer": 42}]

        result = _agentic_code_loop(
            goal="fix analysis",
            system_prompt="sys",
            llm=llm,
            sandbox=sandbox,
            session=mock_session,
            max_turns=1,
        )

        assert sandbox.execute.call_count == 2
        assert "fixed" in result["code"]
        assert result["summary"] == "fixed"
        assert result["plots"] == ["plot.png"]
        assert result["exports"] == ["out.csv"]

    def test_stdout_fallback_summary(self, mock_session):
        llm = MagicMock()
        llm.chat.side_effect = [
            LLMResponse(
                content="",
                model="test",
                content_blocks=[_tool_use_block("print('hello world')")],
            ),
            LLMResponse(content="LGTM - looks good", model="test", content_blocks=[]),
        ]
        sandbox = MagicMock()
        sandbox.execute.return_value = {"stdout": "hello world\n", "error": None, "plots": [], "exports": []}
        sandbox.get_variable.return_value = None

        result = _agentic_code_loop(
            goal="print greeting",
            system_prompt="sys",
            llm=llm,
            sandbox=sandbox,
            session=mock_session,
            max_turns=1,
        )

        assert "hello world" in result["summary"]
