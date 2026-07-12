"""Tests for diagnostics zip export."""

import zipfile
from io import BytesIO

from agent.diagnostics import build_diagnostics_zip, _redact_text


def test_redact_text_masks_home_and_secrets(monkeypatch, tmp_path):
    monkeypatch.setattr("agent.diagnostics._HOME", str(tmp_path))
    text = f"{tmp_path}/Projects/demo sk-ant-abcdefghijklmnopqrstuvwxyz"
    redacted = _redact_text(text)
    assert str(tmp_path) not in redacted
    assert "sk-ant-" not in redacted
    assert "<redacted-secret>" in redacted


def test_build_diagnostics_zip_contains_expected_files():
    data, filename = build_diagnostics_zip(
        version="0.0.0-test",
        doctor_report={
            "ok": True,
            "checked_at": "2026-01-01T00:00:00Z",
            "summary": {"ok": 1, "warn": 0, "error": 0, "total": 1},
            "checks": [],
        },
        ui_diagnostics={"href": "http://localhost:8969/dashboard/doctor"},
    )
    assert filename.endswith(".zip")
    with zipfile.ZipFile(BytesIO(data)) as zf:
        names = zf.namelist()
        joined = "\n".join(names)
        assert "system-info.json" in joined
        assert "doctor-report.json" in joined
        assert "config.redacted.json" in joined
        assert "skills-summary.json" in joined
        assert "ui-diagnostics.json" in joined
        assert "README.md" in joined
        assert "manifest.json" in joined
