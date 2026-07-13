"""HTTP coverage for sandbox settings endpoints."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from agent_server.app import create_app


def test_sandbox_settings_get_and_patch(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("agent.config.CONFIG_DIR", tmp_path / "cfg")
    monkeypatch.setattr("agent.config.CONFIG_FILE", tmp_path / "cfg" / "config.json")
    (tmp_path / "cfg").mkdir(parents=True, exist_ok=True)
    from agent.config import Config

    Config({}).save()

    app = create_app(store_path=tmp_path / "agent.db")
    with TestClient(app) as client:
        get_resp = client.get("/v1/settings/sandbox")
        assert get_resp.status_code == 200
        body = get_resp.json()
        assert body["backend"] == "builtin"
        assert "pipPackages" in body
        assert "modalConfigured" in body

        blocked = client.patch(
            "/v1/settings/sandbox",
            json={"backend": "modal"},
        )
        assert blocked.status_code == 400
        assert "modal_token" in blocked.json()["detail"].lower()

        cfg = Config.load()
        cfg.set("compute.modal_token_id", "ak-test")
        cfg.set("compute.modal_token_secret", "as-test")
        cfg.save()

        patch_resp = client.patch(
            "/v1/settings/sandbox",
            json={
                "backend": "modal",
                "modalApp": "sandwalk-ci",
                "computeType": "cpu",
                "cpuCores": 2,
                "ramGb": 8,
                "idleTtlSeconds": 900,
                "pipPackages": "numpy,pandas",
            },
        )
        assert patch_resp.status_code == 200
        updated = patch_resp.json()
        assert updated["backend"] == "modal"
        assert updated["modalApp"] == "sandwalk-ci"
        assert updated["cpuCores"] == 2
        assert updated["ramGb"] == 8
        assert updated["idleTtlSeconds"] == 900
        assert "numpy" in updated["pipPackages"]
        assert updated["modalConfigured"] is True

        bad = client.patch("/v1/settings/sandbox", json={"backend": "nope"})
        assert bad.status_code == 400


def test_sandbox_settings_probe(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("agent.config.CONFIG_DIR", tmp_path / "cfg")
    monkeypatch.setattr("agent.config.CONFIG_FILE", tmp_path / "cfg" / "config.json")
    (tmp_path / "cfg").mkdir(parents=True, exist_ok=True)
    from agent.config import Config
    from agent.sandbox_probe import ProbeReport, ProbeStep

    Config({}).save()
    app = create_app(store_path=tmp_path / "agent.db")

    fake = ProbeReport(
        ok=True,
        skipped=False,
        steps=[ProbeStep("tokens", True, "set")],
    )
    with (
        TestClient(app) as client,
        patch(
            "agent.sandbox_probe.run_modal_sandbox_probe",
            return_value=fake,
        ),
    ):
        resp = client.post("/v1/settings/sandbox/probe")
        assert resp.status_code == 200
        body = resp.json()
        assert body["ok"] is True
        assert body["steps"][0]["name"] == "tokens"
