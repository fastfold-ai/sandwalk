"""Unit tests for agent_server.status_service helpers."""

from __future__ import annotations

from agent_server import status_service as status


def test_format_platform_label_darwin(monkeypatch):
    monkeypatch.setattr(status.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(status.platform, "mac_ver", lambda: ("15.0", ("", "", ""), ""))
    monkeypatch.setattr(status.platform, "machine", lambda: "arm64")
    label = status._format_platform_label(chip_name="Apple M4")
    assert "Apple M4" in label
    assert "macOS" in label


def test_format_platform_label_linux(monkeypatch):
    monkeypatch.setattr(status.platform, "system", lambda: "Linux")
    monkeypatch.setattr(status.platform, "release", lambda: "6.1")
    monkeypatch.setattr(status.platform, "machine", lambda: "x86_64")
    label = status._format_platform_label()
    assert "Linux" in label


def test_get_status_report_shape(monkeypatch):
    monkeypatch.setenv("FASTFOLD_SERVE_HOST", "127.0.0.1")
    monkeypatch.setenv("FASTFOLD_SERVE_PORT", "8787")
    report = status.get_status_report(version="0.0.1")
    assert report.status == "running"
    assert report.pid > 0
    assert report.uptime_seconds >= 0
    assert report.host == "127.0.0.1"
    assert report.port == 8787
    assert report.system.label
    assert report.cache.path


def test_schedule_stop_dry_run(monkeypatch):
    monkeypatch.setattr(status, "_lifecycle_allowed", lambda: False)
    result = status.schedule_stop()
    assert result.ok is True
    assert result.action == "stop"
    assert "dry-run" in result.message.lower()
