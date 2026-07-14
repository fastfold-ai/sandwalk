"""Unit tests for sandbox probe helpers (no live Modal)."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from agent.sandbox_probe import ProbeReport, modal_tokens_present, run_modal_sandbox_probe


def test_modal_tokens_present_false(monkeypatch):
    monkeypatch.delenv("MODAL_TOKEN_ID", raising=False)
    monkeypatch.delenv("MODAL_TOKEN_SECRET", raising=False)
    cfg = SimpleNamespace(
        get=lambda key, default=None: None,
    )
    with patch("agent.config.sync_process_env_from_config"):
        ok, detail = modal_tokens_present(cfg)
    assert ok is False
    assert "Missing" in detail


def test_modal_tokens_present_true(monkeypatch):
    monkeypatch.setenv("MODAL_TOKEN_ID", "id")
    monkeypatch.setenv("MODAL_TOKEN_SECRET", "secret")
    cfg = SimpleNamespace(get=lambda key, default=None: None)
    with patch("agent.config.sync_process_env_from_config"):
        ok, detail = modal_tokens_present(cfg)
    assert ok is True
    assert "set" in detail


def test_probe_skipped_without_tokens(monkeypatch):
    monkeypatch.delenv("MODAL_TOKEN_ID", raising=False)
    monkeypatch.delenv("MODAL_TOKEN_SECRET", raising=False)
    cfg = SimpleNamespace(get=lambda key, default=None: None, set=lambda *a, **k: None)
    with patch("agent.config.Config.load", return_value=cfg):
        with patch("agent.config.sync_process_env_from_config"):
            report = run_modal_sandbox_probe(config=cfg, terminate=True)
    assert report.skipped is True
    assert report.ok is False
    assert report.to_dict()["skipped"] is True


def test_probe_mocked_success(monkeypatch, tmp_path):
    monkeypatch.setenv("MODAL_TOKEN_ID", "id")
    monkeypatch.setenv("MODAL_TOKEN_SECRET", "secret")

    fake_backend = MagicMock()

    def _exec(cmd, *, timeout=None):
        if "cat /workspace/hello.txt" in cmd:
            return SimpleNamespace(output="hello-from-host\n", exit_code=0)
        if "test -f /skills" in cmd or "SKILLS_OK" in cmd or "WORKSPACE_OK" in cmd:
            return SimpleNamespace(output="SKILLS_OK\n", exit_code=0)
        if "mkdir -p" in cmd:
            return SimpleNamespace(output="", exit_code=0)
        if "probe.py" in cmd or "python" in cmd:
            return SimpleNamespace(output="", exit_code=0)
        return SimpleNamespace(output="", exit_code=0)

    fake_backend.execute.side_effect = _exec
    fake_backend.upload_files.return_value = []
    fake_backend.read.return_value = SimpleNamespace(
        error=None,
        file_data={"content": "---\nname: e2e_probe\n---\n\n# Probe\n", "encoding": "utf-8"},
    )

    handle = MagicMock()
    handle.kind = "modal"
    handle.provider_sandbox_name = "sandwalk-probe"
    handle.backend = fake_backend

    def _pull():
        # Mimic probe writing out.txt into the temp workspace used by probe.
        return 1

    handle.pull.side_effect = _pull
    handle.terminate = MagicMock()

    cfg = SimpleNamespace(
        get=lambda key, default=None: "builtin",
        set=lambda *a, **k: None,
    )

    real_resolve = None

    def _fake_resolve(config, *, session_id, workspace_root, skill_source_dirs=None):
        # Write the expected pull artifact into the probe temp dir.
        from pathlib import Path

        Path(workspace_root, "out.txt").write_text("probe-ok\n", encoding="utf-8")
        return handle

    with patch("agent.config.sync_process_env_from_config"):
        with patch(
            "agent.sandbox_deps.ensure_modal_deps",
            return_value=(True, "langchain-modal and modal importable"),
        ):
            with patch(
                "agent.sandbox_backend.resolve_deepagents_backend",
                side_effect=_fake_resolve,
            ):
                report = run_modal_sandbox_probe(config=cfg, terminate=True)

    assert report.skipped is False
    assert report.ok is True
    handle.terminate.assert_called()


def test_probe_auto_heals_missing_deps(monkeypatch):
    monkeypatch.setenv("MODAL_TOKEN_ID", "id")
    monkeypatch.setenv("MODAL_TOKEN_SECRET", "secret")
    cfg = SimpleNamespace(get=lambda key, default=None: None, set=lambda *a, **k: None)

    with patch("agent.config.Config.load", return_value=cfg):
        with patch("agent.config.sync_process_env_from_config"):
            with patch(
                "agent.sandbox_deps.ensure_modal_deps",
                return_value=(False, "auto-install failed"),
            ):
                report = run_modal_sandbox_probe(config=cfg, terminate=True)

    assert report.ok is False
    assert report.skipped is True
    assert any(step.name == "deps" and not step.ok for step in report.steps)


def test_probe_report_dict():
    report = ProbeReport(
        ok=True,
        skipped=False,
        steps=[],
    )
    assert report.to_dict() == {"ok": True, "skipped": False, "steps": []}
