"""Service-layer tests for sandbox settings."""

from __future__ import annotations

from pathlib import Path

import pytest

from agent.config import Config
from agent_server.models import UpdateSandboxSettingsRequest
from agent_server.sandbox_settings_service import SandboxSettingsService


def test_sandbox_settings_service_roundtrip(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("agent.config.CONFIG_DIR", tmp_path / "cfg")
    monkeypatch.setattr("agent.config.CONFIG_FILE", tmp_path / "cfg" / "config.json")
    (tmp_path / "cfg").mkdir(parents=True, exist_ok=True)
    Config({}).save()

    current = SandboxSettingsService.get()
    assert current.backend == "builtin"

    with pytest.raises(ValueError, match="modal_token"):
        SandboxSettingsService.update(UpdateSandboxSettingsRequest(backend="modal"))

    cfg = Config.load()
    cfg.set("compute.modal_token_id", "ak-test")
    cfg.set("compute.modal_token_secret", "as-test")
    cfg.save()

    updated = SandboxSettingsService.update(
        UpdateSandboxSettingsRequest(
            backend="modal",
            modal_app="demo",
            compute_type="gpu",
            gpu_class="A10G",
            cpu_cores=1.5,
            ram_gb=16,
            idle_ttl_seconds=120,
            pip_packages="scipy",
        )
    )
    assert updated.backend == "modal"
    assert updated.modal_app == "demo"
    assert updated.compute_type == "gpu"
    assert updated.gpu_class == "A10G"
    assert updated.pip_packages == "scipy"
    assert updated.modal_configured is True

    cfg = Config.load()
    assert cfg.get("sandbox.backend") == "modal"

    with pytest.raises(ValueError):
        SandboxSettingsService.update(UpdateSandboxSettingsRequest(backend="xyz"))
