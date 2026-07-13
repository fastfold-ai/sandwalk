"""HTTP coverage for runtime settings endpoints."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from agent_server.app import create_app


def test_runtime_settings_get_and_patch(tmp_path: Path):
    app = create_app(store_path=tmp_path / "agent.db")
    with TestClient(app) as client:
        get_resp = client.get("/v1/settings/runtime")
        assert get_resp.status_code == 200
        body = get_resp.json()
        assert "recursionLimit" in body
        assert "maxSdkTurns" in body
        assert "toolMode" in body

        patch_resp = client.patch(
            "/v1/settings/runtime",
            json={
                "recursionLimit": 150,
                "maxSdkTurns": 35,
                "toolMode": "native",
                "groupToolTraces": False,
                "toolHealthEnabled": True,
            },
        )
        assert patch_resp.status_code == 200
        updated = patch_resp.json()
        assert updated["recursionLimit"] == 150
        assert updated["maxSdkTurns"] == 35
        assert updated["toolMode"] == "native"
        assert updated["groupToolTraces"] is False
