"""Coverage for event-processor progress, token estimates, and the sandbox namespace."""

from __future__ import annotations

from types import SimpleNamespace

from agent.deepagents_runtime.event_processor.core import EventProcessorCoreMixin
from agent.sandbox.namespace_setup import SandboxSetupMixin
from agent_server.prompt_budget_service.tokens import (
    bucket_from_text,
    estimate_tokens,
    tool_schema_text,
)


def test_event_processor_progress_spinner_and_usage(monkeypatch) -> None:
    seen: list[tuple] = []

    def legacy(text):
        seen.append(("legacy", text))

    processor = EventProcessorCoreMixin(on_activity=legacy, headless=True)
    processor._emit_progress("activity", text=" working ")
    assert seen == [("legacy", "working")]

    def broken(_event, **_payload):
        raise RuntimeError("no")

    processor.on_activity = broken
    processor._emit_progress("activity", text="x")

    spinner = SimpleNamespace(stopped=False)

    def stop():
        spinner.stopped = True

    spinner.stop = stop
    runner = SimpleNamespace(_active_spinner=spinner)
    processor.runner = runner
    processor.spinner["obj"] = spinner
    processor._stop_spinner()
    assert spinner.stopped is True
    assert runner._active_spinner is None

    processor.allow_live_spinner = True
    processor.headless = False
    processor.trace_renderer = SimpleNamespace(console=object())
    processor.spinner["obj"] = None
    processor._start_evaluating_spinner()
    processor.spinner["obj"] = object()
    processor._start_evaluating_spinner()

    processor.on_activity = lambda event, **payload: seen.append((event, payload))
    processor._add_usage(SimpleNamespace())
    monkeypatch.setattr(
        "agent.deepagents_runtime.event_processor.core._usage_from_message",
        lambda _message: {"input_tokens": 2, "tokens_per_second": 1.5, "estimated": True},
    )
    processor._add_usage(SimpleNamespace())
    assert processor.token_usage["input_tokens"] == 2
    assert any(item[0] == "usage" for item in seen)


def test_token_estimates_and_tool_schema(monkeypatch) -> None:
    assert estimate_tokens("") == (0, "tiktoken")
    tokens, label = estimate_tokens("hello", model="not-a-real-model")
    assert tokens > 0
    assert label.startswith("tiktoken") or label == "chars/4"

    real_import = __import__

    def hide_tiktoken(name, *args, **kwargs):
        if name == "tiktoken":
            raise ImportError("tiktoken")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", hide_tiktoken)
    assert estimate_tokens("abcd") == (1, "chars/4")

    class Schema:
        def model_json_schema(self):
            return {"type": "object"}

    tool = SimpleNamespace(name="read", description="Read a file", args_schema=Schema())
    text = tool_schema_text(tool)
    assert "read" in text

    class Boom:
        def model_json_schema(self):
            raise RuntimeError("schema")

    dumped = tool_schema_text(SimpleNamespace(name="x", description="", args_schema=Boom()))
    assert dumped.startswith("x")
    raw = tool_schema_text(SimpleNamespace(name="y", description="d", args_schema={"a": 1}))
    assert '"a": 1' in raw
    bucket = bucket_from_text(id="tools", label="Tools", text="abcd", model=None, count=1)
    assert bucket.chars == 4


def test_sandbox_namespace_includes_pi_helper(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("SANDWALK_ENABLE_R", "yes")
    box = SandboxSetupMixin(output_dir=tmp_path, extra_read_dirs=[tmp_path])
    pi = box._namespace["compute_pi_percentage"]
    assert pi([]) == 0.0
    assert pi(["AT", "AT"]) == 0.0
    score = pi(["ATGC", "ATGG", "AT-C"])
    assert score >= 0
    assert callable(box._namespace["__builtins__"]["open"])
    assert callable(box._namespace["safe_subprocess_run"])
