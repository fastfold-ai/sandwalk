"""A failed OAuth refresh is not retried on every agent turn."""

from __future__ import annotations

import pytest

from agent.config import Config
from agent.mcp_catalog import McpCatalogEntry
from agent_server.mcp_service import auth


@pytest.fixture(autouse=True)
def _reset_backoff():
    auth.clear_oauth_refresh_backoff()
    yield
    auth.clear_oauth_refresh_backoff()


def _entry() -> McpCatalogEntry:
    return McpCatalogEntry(
        id="tavily",
        name="Tavily",
        description="test",
        url="https://mcp.example.test/mcp",
        auth_mode="oauth",
    )


def _expired_cfg() -> Config:
    return Config(
        data={
            "mcp.tavily_access_token": "old",
            "mcp.tavily_refresh_token": "dead",
            "mcp.tavily_client_id": "cid",
            "mcp.tavily_token_endpoint": "https://mcp.example.test/token",
            "mcp.tavily_token_expires_at": 1.0,  # long expired
        }
    )


def test_failed_refresh_backs_off(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = 0

    def fake_refresh(**kwargs):
        nonlocal calls
        calls += 1
        return None

    monkeypatch.setattr(auth, "_refresh_oauth_access_token", fake_refresh)
    monkeypatch.setattr(auth, "oauth_access_token_expired", lambda entry, cfg: True)
    entry = _entry()
    cfg = _expired_cfg()

    assert auth.ensure_fresh_catalog_oauth_token(entry, cfg) is None
    # Next turns: no network call.
    assert auth.ensure_fresh_catalog_oauth_token(entry, cfg) is None
    assert auth.ensure_fresh_catalog_oauth_token(entry, cfg) is None
    assert calls == 1


def test_backoff_expires_and_clears_on_success(monkeypatch: pytest.MonkeyPatch) -> None:
    results = iter([None, "fresh-token"])
    calls = 0

    def fake_refresh(**kwargs):
        nonlocal calls
        calls += 1
        return next(results)

    monkeypatch.setattr(auth, "_refresh_oauth_access_token", fake_refresh)
    monkeypatch.setattr(auth, "oauth_access_token_expired", lambda entry, cfg: True)
    now = [1000.0]
    monkeypatch.setattr(auth.time, "monotonic", lambda: now[0])
    entry = _entry()
    cfg = _expired_cfg()

    assert auth.ensure_fresh_catalog_oauth_token(entry, cfg) is None
    now[0] += auth.REFRESH_BACKOFF_SEC + 1
    assert auth.ensure_fresh_catalog_oauth_token(entry, cfg) == "fresh-token"
    assert calls == 2
    # Success cleared the backoff: a later expiry refreshes immediately.
    assert not auth._refresh_backed_off("tavily")


def test_reconnect_clears_backoff(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(auth, "_refresh_oauth_access_token", lambda **kw: None)
    monkeypatch.setattr(auth, "oauth_access_token_expired", lambda entry, cfg: True)
    entry = _entry()
    auth.ensure_fresh_catalog_oauth_token(entry, _expired_cfg())
    assert auth._refresh_backed_off("tavily")
    auth.clear_oauth_refresh_backoff("tavily")
    assert not auth._refresh_backed_off("tavily")
