"""Empty model turns (no text, no tool calls) keep their stop reason."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

from agent.deepagents_runtime.event_processor import process_events
from agent.runner.deepagents_build import _empty_output_summary
from agent.runner.deepagents_run import _merge_deepagents_chunks


async def _events(*items):
    for item in items:
        yield item


def _run(events):
    return asyncio.run(process_events(_events(*events), headless=True))


def test_empty_turn_records_stop_reason_and_blocks() -> None:
    output = SimpleNamespace(
        content=[{"type": "thinking", "thinking": ""}],
        tool_calls=[],
        response_metadata={"stop_reason": "refusal", "model": "claude-fable-5-1"},
    )
    result = _run([{"event": "on_chat_model_end", "data": {"output": output}}])
    assert result["full_text"] == []
    assert result["empty_model_turns"] == [
        {
            "call": 1,
            "stop_reason": "refusal",
            "content_blocks": ["thinking"],
            "model": "claude-fable-5-1",
        }
    ]


def test_tool_only_turn_is_not_flagged() -> None:
    output = SimpleNamespace(
        content="",
        tool_calls=[{"name": "ls", "args": {}, "id": "t1"}],
        response_metadata={"stop_reason": "tool_use"},
    )
    result = _run([{"event": "on_chat_model_end", "data": {"output": output}}])
    assert result["empty_model_turns"] == []


def test_text_turn_is_not_flagged() -> None:
    output = SimpleNamespace(content="ZQX7", tool_calls=[], response_metadata={})
    result = _run([{"event": "on_chat_model_end", "data": {"output": output}}])
    assert result["full_text"] == ["ZQX7"]
    assert result["empty_model_turns"] == []


def test_merge_keeps_empty_turns_across_resume_loops() -> None:
    acc = {"full_text": [], "tool_calls": [], "token_usage": {}, "model_call_count": 1,
           "empty_model_turns": [{"call": 1, "stop_reason": "max_tokens"}]}
    chunk = {"full_text": [], "tool_calls": [], "token_usage": {}, "model_call_count": 1,
             "empty_model_turns": [{"call": 1, "stop_reason": "refusal"}]}
    merged = _merge_deepagents_chunks(acc, chunk)
    assert [t["stop_reason"] for t in merged["empty_model_turns"]] == ["max_tokens", "refusal"]


def test_summary_mentions_stop_reason() -> None:
    assert _empty_output_summary(None) == "(Agent produced no text output)"
    assert _empty_output_summary([]) == "(Agent produced no text output)"
    assert (
        _empty_output_summary([{"stop_reason": "refusal", "content_blocks": ["thinking"]}])
        == "(Agent produced no text output — model returned stop_reason=refusal; content=thinking)"
    )
    assert _empty_output_summary([{"stop_reason": None, "content_blocks": []}]) == (
        "(Agent produced no text output)"
    )
