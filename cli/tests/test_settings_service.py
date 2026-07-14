"""Unit tests for agent_server.settings_service runtime overrides."""

from __future__ import annotations

from pathlib import Path

from agent.config import Config
from agent_server.models import UpdateRuntimeSettingsRequest
from agent_server.settings_service import SettingsService


def test_settings_service_get_defaults(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("agent.config.CONFIG_DIR", tmp_path / "cfg")
    monkeypatch.setattr("agent.config.CONFIG_FILE", tmp_path / "cfg" / "config.json")
    (tmp_path / "cfg").mkdir(parents=True, exist_ok=True)
    Config({}).save()

    settings = SettingsService.get()
    assert settings.provider
    assert settings.model
    assert settings.tool_mode in {"ptc", "native"}
    assert settings.reasoning_effort in {"low", "medium", "high"}
    assert settings.reasoning_fast is False
    assert settings.recursion_limit >= 25
    assert settings.max_sdk_turns >= 1
    assert isinstance(settings.group_tool_traces, bool)
    assert settings.tool_trace_detail_limit >= 1
    assert settings.background_watch_timeout_s >= 60
    assert settings.interrupt_drain_timeout_s >= 1
    assert settings.parallel_max_threads >= 1
    assert isinstance(settings.tool_health_enabled, bool)


def test_settings_service_update_runtime_knobs(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("agent.config.CONFIG_DIR", tmp_path / "cfg")
    monkeypatch.setattr("agent.config.CONFIG_FILE", tmp_path / "cfg" / "config.json")
    (tmp_path / "cfg").mkdir(parents=True, exist_ok=True)
    Config({}).save()

    updated = SettingsService.update(
        UpdateRuntimeSettingsRequest(
            tool_mode="native",
            provider="openai",
            model="gpt-5.6-sol",
            reasoning_effort="high",
            reasoning_fast=True,
            recursion_limit=200,
            max_sdk_turns=40,
            group_tool_traces=False,
            tool_trace_detail_limit=3,
            background_watch_timeout_s=3600,
            interrupt_drain_timeout_s=30,
            parallel_max_threads=4,
            tool_health_enabled=False,
            tool_health_fail_threshold=5,
            tool_health_suppress_seconds=600,
        )
    )
    assert updated.tool_mode == "native"
    assert updated.reasoning_effort == "high"
    assert updated.reasoning_fast is True
    assert updated.recursion_limit == 200
    assert updated.max_sdk_turns == 40
    assert updated.group_tool_traces is False
    assert updated.tool_trace_detail_limit == 3
    assert updated.background_watch_timeout_s == 3600
    assert updated.interrupt_drain_timeout_s == 30
    assert updated.parallel_max_threads == 4
    assert updated.tool_health_enabled is False
    assert updated.tool_health_fail_threshold == 5
    assert updated.tool_health_suppress_seconds == 600

    cfg = Config.load()
    assert cfg.get("agent.tool_mode") == "native"
    assert cfg.get("llm.reasoning_effort") == "high"
    assert cfg.get("llm.reasoning_fast") is True
    store = cfg.get("llm.model_reasoning") or {}
    assert store["openai:gpt-5.6-sol"]["effort"] == "high"
    assert store["openai:gpt-5.6-sol"]["fast"] is True
    assert int(cfg.get("agent.recursion_limit")) == 200
    assert int(cfg.get("agent.max_sdk_turns")) == 40

    # Per-model: changing another model must not clobber Sol's effort.
    SettingsService.update(
        UpdateRuntimeSettingsRequest(
            provider="anthropic",
            model="claude-sonnet-5",
            reasoning_effort="low",
            reasoning_fast=False,
        )
    )
    cfg = Config.load()
    store = cfg.get("llm.model_reasoning") or {}
    assert store["openai:gpt-5.6-sol"]["effort"] == "high"
    assert store["openai:gpt-5.6-sol"]["fast"] is True
    assert store["anthropic:claude-sonnet-5"]["effort"] == "low"
    assert store["anthropic:claude-sonnet-5"]["fast"] is False
    sonnet = SettingsService.get()
    assert sonnet.model == "claude-sonnet-5"
    assert sonnet.reasoning_effort == "low"
    assert sonnet.reasoning_fast is False


def test_settings_service_onboarding(tmp_path: Path, monkeypatch):
    from agent_server.models import UpdateOnboardingSettingsRequest

    monkeypatch.setattr("agent.config.CONFIG_DIR", tmp_path / "cfg")
    monkeypatch.setattr("agent.config.CONFIG_FILE", tmp_path / "cfg" / "config.json")
    (tmp_path / "cfg").mkdir(parents=True, exist_ok=True)
    Config({}).save()

    current = SettingsService.get_onboarding()
    assert current.completed is False
    assert current.step == 0

    updated = SettingsService.update_onboarding(
        UpdateOnboardingSettingsRequest(step=3, completed=False)
    )
    assert updated.step == 3
    assert updated.completed is False

    done = SettingsService.update_onboarding(
        UpdateOnboardingSettingsRequest(completed=True, step=6)
    )
    assert done.completed is True
    assert done.step == 6

    clamped = SettingsService.update_onboarding(
        UpdateOnboardingSettingsRequest(step=99)
    )
    assert clamped.step == 6


def test_settings_service_clamps_out_of_range(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("agent.config.CONFIG_DIR", tmp_path / "cfg")
    monkeypatch.setattr("agent.config.CONFIG_FILE", tmp_path / "cfg" / "config.json")
    (tmp_path / "cfg").mkdir(parents=True, exist_ok=True)
    Config({}).save()

    updated = SettingsService.update(
        UpdateRuntimeSettingsRequest(
            recursion_limit=5,
            max_sdk_turns=0,
            tool_trace_detail_limit=999,
            parallel_max_threads=100,
        )
    )
    assert updated.recursion_limit == 25
    assert updated.max_sdk_turns == 1
    assert updated.tool_trace_detail_limit == 50
    assert updated.parallel_max_threads == 20
