"""Unit tests for Sandwalk Fastfold one-click grant import."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from agent_server.integrations_service import fastfold_one_click as ff


def test_start_fastfold_one_click_stores_claim_token(monkeypatch):
    ff.clear_fastfold_one_click()

    def fake_cloud(method, url, *, body=None, bearer=None):
        assert method == "POST"
        assert url.endswith("/v1/sandwalk/oauth/start")
        assert body and "return_to" in body
        assert body.get("device_label")
        assert "@ sandwalk " in body["device_label"]
        assert "python-v" in body["device_label"]
        assert body.get("client_ip") == "186.28.32.75"
        assert body.get("location") == "Bogotá, Colombia"
        return {
            "auth_url": "https://cloud.fastfold.ai/connect/sandwalk?state=abc",
            "claim_token": "claim-123",
        }, None

    monkeypatch.setattr(
        ff,
        "_network_meta",
        lambda: {"client_ip": "186.28.32.75", "location": "Bogotá, Colombia"},
    )
    monkeypatch.setattr(ff, "_cloud_json", fake_cloud)
    monkeypatch.setattr(ff, "cloud_base_url", lambda: "http://127.0.0.1:8000")
    url = ff.start_fastfold_one_click(return_to="http://127.0.0.1:8787/oauth/callback")
    assert url.startswith("http://localhost:3000/connect/sandwalk")
    assert ff._pending_claim_token == "claim-123"


def test_import_fastfold_one_click_not_ready(monkeypatch):
    ff.clear_fastfold_one_click()
    ff._pending_claim_token = "claim-123"

    monkeypatch.setattr(
        ff,
        "_cloud_json",
        lambda *a, **k: (None, "not_ready"),
    )
    result = ff.import_fastfold_one_click(MagicMock())
    assert result == {"ready": False}
    assert ff._pending_claim_token == "claim-123"


def test_import_fastfold_one_click_persists_key(monkeypatch):
    ff.clear_fastfold_one_click()
    ff._pending_claim_token = "claim-123"
    integrations = MagicMock()
    provider = MagicMock()
    integrations.update.return_value = provider

    monkeypatch.setattr(
        ff,
        "_cloud_json",
        lambda *a, **k: ({"api_key": "sk-test-key", "team_id": None}, None),
    )

    result = ff.import_fastfold_one_click(integrations)
    assert result["ready"] is True
    assert result["provider"] is provider
    integrations.update.assert_called_once_with(
        "fastfold-cloud", {"FASTFOLD_API_KEY": "sk-test-key"}
    )
    assert ff._pending_claim_token is None


def test_local_oauth_return_url_rewrites_wildcard_bind(monkeypatch):
    from agent_server.connectors.service import local_oauth_return_url

    monkeypatch.setenv("FASTFOLD_SERVE_HOST", "0.0.0.0")
    monkeypatch.setenv("FASTFOLD_SERVE_PORT", "8787")
    assert local_oauth_return_url() == "http://127.0.0.1:8787/oauth/callback"
    ff.clear_fastfold_one_click()
    with pytest.raises(ValueError, match="No Sandwalk allow"):
        ff.import_fastfold_one_click(MagicMock())


def test_oauth_callback_return_to_uses_lan_origin_not_wildcard_bind(monkeypatch):
    from agent_server.connectors.service import oauth_callback_return_to

    monkeypatch.setenv("FASTFOLD_SERVE_HOST", "0.0.0.0")
    monkeypatch.setenv("FASTFOLD_SERVE_PORT", "8787")
    assert (
        oauth_callback_return_to(
            origin="http://192.168.2.178:8787",
            base_url="http://0.0.0.0:8787/",
        )
        == "http://192.168.2.178:8787/oauth/callback"
    )
    assert (
        oauth_callback_return_to(origin=None, base_url="http://192.168.2.178:8787/")
        == "http://192.168.2.178:8787/oauth/callback"
    )
    assert (
        oauth_callback_return_to(origin=None, base_url="http://0.0.0.0:8787/")
        == "http://127.0.0.1:8787/oauth/callback"
    )
