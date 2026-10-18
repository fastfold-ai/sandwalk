"""Deep Agents run failures: missing runtime, transport retry, and classified errors."""

from __future__ import annotations

import asyncio
import sys
from types import ModuleType, SimpleNamespace

from agent.runner.deepagents_run import DeepAgentsRunMixin


class _Config:
    def __init__(self, provider="openai"):
        self.provider = provider
        self.raises = None

    def get(self, key, default=None):
        if self.raises is not None:
            raise self.raises
        if key == "llm.provider":
            return self.provider
        return default

    def model_setup_message(self):
        return ""


class _Runner(DeepAgentsRunMixin):
    def __init__(self):
        self.session = SimpleNamespace(config=_Config(), console=None)
        self._headless = True
        self.errors = []

    def _make_error_result(self, query, message, elapsed, prefix_sdk=True):
        return message

    def _print_friendly_error(self, title, body):
        self.errors.append((title, body))


def test_runtime_import_failure(monkeypatch):
    boom = ModuleType("deepagents")

    def _missing(name):
        raise ImportError("deepagents missing")

    boom.__getattr__ = _missing
    monkeypatch.setitem(sys.modules, "deepagents", boom)
    message = asyncio.run(_Runner()._run_async_deepagents("fold this"))
    assert "not available" in message


def test_retry_then_classified_error(monkeypatch):
    state = {"n": 0}

    def _build(config):
        state["n"] += 1
        if state["n"] == 1:
            raise ValueError("no model")
        raise RuntimeError("reset")

    def _transient(exc):
        return state["n"] == 2

    def _heal(config, exc):
        return state["n"] == 3

    def _classify(exc):
        if state["n"] < 5:
            return ("Rate limit", "slow down\nmore")
        return None

    monkeypatch.setattr("agent.deepagents_runtime.build_chat_model", _build)
    monkeypatch.setattr("agent.runner.deepagents_run._is_transient_transport_error", _transient)
    monkeypatch.setattr("agent.model_catalog.param_heal.apply_param_heal_from_error", _heal)
    monkeypatch.setattr("agent.runner.deepagents_run._classify_llm_error", _classify)
    runner = _Runner()

    def _progress(event, **payload):
        raise RuntimeError("ui")

    missing = asyncio.run(runner._run_async_deepagents("fold"))
    assert "no model" in missing
    classified = asyncio.run(runner._run_async_deepagents("fold", progress_callback=_progress))
    assert classified.startswith("Rate limit")
    plain = asyncio.run(runner._run_async_deepagents("fold", progress_callback=_progress))
    assert "reset" in plain

    def _interrupt(config):
        raise InterruptedError("stop")

    monkeypatch.setattr("agent.deepagents_runtime.build_chat_model", _interrupt)
    try:
        asyncio.run(runner._run_async_deepagents("fold"))
        raise AssertionError("expected interrupt")
    except InterruptedError:
        pass
