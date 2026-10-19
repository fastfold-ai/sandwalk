"""Offline mode and Apple GPU metric parsing without live probes."""

from __future__ import annotations

import plistlib
import subprocess

import pytest

from agent_server import offline_mode
from agent_server.status_service import gpu_metrics


def test_offline_mode_flags_and_probes(monkeypatch):
    monkeypatch.delenv("SANDWALK_FORCE_OFFLINE", raising=False)
    monkeypatch.delenv("SANDWALK_SILENT_OFFLINE", raising=False)
    offline_mode.force_offline(False)
    assert offline_mode.is_offline() is False
    assert offline_mode.get_degraded_features() == []
    assert offline_mode.is_feature_available("slack") is True
    assert offline_mode.skip_if_offline() is False
    assert offline_mode.should_use_builtin_sandbox() is False

    offline_mode.force_offline(True, "test")
    assert offline_mode.is_offline() is True
    assert offline_mode.get_offline_reason() == "test"
    assert "Slack" in " ".join(offline_mode.get_degraded_features())
    assert offline_mode.is_feature_available("slack") is False
    assert offline_mode.is_feature_available("local-chat") is True
    assert offline_mode.should_skip_slack_connectors() is True
    assert offline_mode.should_skip_mcp_oauth_refresh() is True
    assert offline_mode.should_skip_aws_credential_refresh() is True
    assert offline_mode.should_skip_cloud_model_probes() is True
    state = offline_mode.get_offline_state()
    assert state["reason"] == "test"
    ui = offline_mode.get_ui_status()
    assert ui["is_offline"] is True

    monkeypatch.setenv("SANDWALK_FORCE_OFFLINE", "1")
    assert offline_mode.get_offline_state()["forced"] is True
    offline_mode._check_network_health()
    assert offline_mode._offline_reason == "force_offline"

    monkeypatch.setenv("SANDWALK_FORCE_OFFLINE", "0")
    monkeypatch.setenv("SANDWALK_SILENT_OFFLINE", "1")
    offline_mode._check_network_health()
    assert offline_mode.is_offline() is False

    monkeypatch.delenv("SANDWALK_SILENT_OFFLINE")
    offline_mode.set_probe_targets(["one.example", "two.example"])
    monkeypatch.setattr(offline_mode, "_tcp_reachable", lambda host, port, timeout=1.5: host == "one.example")
    offline_mode._check_network_health()
    assert offline_mode.is_offline() is False

    monkeypatch.setattr(offline_mode, "_tcp_reachable", lambda host, port, timeout=1.5: False)
    offline_mode._check_network_health()
    assert offline_mode.is_offline() is True
    assert "unreachable" in (offline_mode.get_offline_reason() or "")

    def _down(*_a, **_k):
        raise OSError("no")

    monkeypatch.setattr(offline_mode.socket, "create_connection", _down)
    assert offline_mode._tcp_reachable("example.com", 443) is False

    async def _online():
        monkeypatch.setattr(offline_mode, "_tcp_reachable", lambda *a, **k: True)
        assert await offline_mode.check_network_health_async() is True
        await offline_mode.init_offline_mode()

    import asyncio

    asyncio.run(_online())
    offline_mode.force_offline(False)


def test_gpu_metrics(monkeypatch):
    monkeypatch.setattr(gpu_metrics.platform, "system", lambda: "Linux")
    assert gpu_metrics._chip_name() is None
    assert gpu_metrics._gpu_core_count_from_profiler() is None
    assert gpu_metrics._gpu_metrics_darwin()["gpu_cores"] is None

    monkeypatch.setattr(gpu_metrics.platform, "system", lambda: "Darwin")

    def _sysctl(*_a, **_k):
        return subprocess.CompletedProcess([], 0, "Apple M4\n", "")

    monkeypatch.setattr(gpu_metrics.subprocess, "run", _sysctl)
    assert gpu_metrics._chip_name() == "Apple M4"

    def _timeout(*_a, **_k):
        raise subprocess.TimeoutExpired(cmd="sysctl", timeout=1)

    monkeypatch.setattr(gpu_metrics.subprocess, "run", _timeout)
    assert gpu_metrics._chip_name() is None

    def _profiler(*_a, **_k):
        return subprocess.CompletedProcess([], 0, "Total Number of Cores: 10\n", "")

    monkeypatch.setattr(gpu_metrics.subprocess, "run", _profiler)
    assert gpu_metrics._gpu_core_count_from_profiler() == 10

    blob = plistlib.dumps(
        [
            {
                "gpu-core-count": 10,
                "PerformanceStatistics": {
                    "Device Utilization %": 140,
                    "In use system memory": 1024,
                    "Alloc system memory": 4096,
                },
            }
        ]
    )

    def _ioreg(cmd, **_k):
        if cmd[0] == "ioreg":
            return subprocess.CompletedProcess(cmd, 0, blob, b"")
        return subprocess.CompletedProcess(cmd, 0, "Total Number of Cores: 8\n", "")

    monkeypatch.setattr(gpu_metrics.subprocess, "run", _ioreg)
    metrics = gpu_metrics._gpu_metrics_darwin()
    assert metrics["gpu_cores"] == 10
    assert metrics["gpu_utilization_percent"] == 100.0
    assert metrics["gpu_memory_used_bytes"] == 1024
    assert metrics["gpu_memory_total_bytes"] == 4096
