"""Tests for local General settings account resolution."""

from __future__ import annotations

from agent_server.account_service import AccountService, _format_plan_label
from agent_server.models import AccountSummary


def test_format_plan_label():
    assert _format_plan_label("pro") == "Pro"
    assert _format_plan_label("pro_plus") == "Pro+"
    assert _format_plan_label("") == ""


def test_account_without_api_key(monkeypatch):
    monkeypatch.delenv("FASTFOLD_API_KEY", raising=False)

    class FakeConfig:
        def get(self, key, default=None):
            return default

    monkeypatch.setattr("agent_server.account_service.Config.load", FakeConfig)
    summary = AccountService().get(version="1.2.3", check_updates=False)
    assert isinstance(summary, AccountSummary)
    assert summary.configured is False
    assert summary.user is None
    assert summary.about.version == "1.2.3"
    assert summary.about.channel == "default"


def test_account_with_api_key_fetches_user(monkeypatch):
    monkeypatch.setenv("FASTFOLD_API_KEY", "sk-test")

    class FakeConfig:
        def get(self, key, default=None):
            return default

    def fake_request(url: str, api_key: str, *, timeout: float = 4.0):
        if url.endswith("/v1/users/me"):
            return {
                "id": "user-1",
                "email": "jc@example.com",
                "username": "jc",
            }
        if url.endswith("/v1/billing/workspaces/plans"):
            return {
                "items": [
                    {
                        "workspace_id": "ws-1",
                        "workspace_type": "personal",
                        "team_id": None,
                        "plan_code": "pro",
                    }
                ]
            }
        return None

    monkeypatch.setattr("agent_server.account_service.Config.load", FakeConfig)
    monkeypatch.setattr("agent_server.account_service._request_json", fake_request)

    summary = AccountService().get(version="9.9.9", check_updates=False)
    assert summary.configured is True
    assert summary.user is not None
    assert summary.user.email == "jc@example.com"
    assert summary.user.plan_label == "Pro plan"
    assert summary.organization is not None
    assert summary.organization.id == "ws-1"
    assert summary.organization.name == "jc@example.com's Organization"
