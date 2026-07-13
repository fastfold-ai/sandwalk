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
    assert int(cfg.get("agent.recursion_limit")) == 200
    assert int(cfg.get("agent.max_sdk_turns")) == 40


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
