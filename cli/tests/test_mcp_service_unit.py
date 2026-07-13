"""Unit tests for agent_server.mcp_service helpers and McpService."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from agent.config import Config
from agent.mcp_catalog import get_catalog_entry
from agent_server.mcp_service import (
    McpService,
    auth_method_in_use,
    clear_custom_headers,
    clear_health_cache,
    clear_tool_count,
    credentials_configured,
    enrich_mcp_server,
    get_custom_headers,
    parse_sse_or_json,
    read_status_message,
    read_tool_count,
    resolve_auth_headers,
    save_status_message,
    save_tool_count,
    set_custom_headers,
)
from agent_server.store import AgentStore


def test_get_custom_headers_dict_and_json_string():
    cfg = MagicMock()
    cfg.get.return_value = {"X-Key": "value"}
    assert get_custom_headers(cfg, "srv1") == {"X-Key": "value"}

    cfg.get.return_value = json.dumps({"Authorization": "Bearer tok"})
    assert get_custom_headers(cfg, "srv1") == {"Authorization": "Bearer tok"}

    cfg.get.return_value = "not-json"
    assert get_custom_headers(cfg, "srv1") == {}


def test_set_and_clear_custom_headers(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("agent.config.CONFIG_DIR", tmp_path / "cfg")
    monkeypatch.setattr("agent.config.CONFIG_FILE", tmp_path / "cfg" / "config.json")
    (tmp_path / "cfg").mkdir(parents=True, exist_ok=True)
    cfg = Config({})
    cfg.save()

    set_custom_headers("abc", {"X-Test": "1"}, config=cfg)
    reloaded = Config.load()
    assert get_custom_headers(reloaded, "abc") == {"X-Test": "1"}

    clear_custom_headers("abc", config=reloaded)
    assert get_custom_headers(Config.load(), "abc") == {}


def test_enrich_mcp_server_attaches_header_metadata():
    server = MagicMock()
    server.id = "s1"
    server.model_copy = lambda update: MagicMock(**{**server.__dict__, **update})
    cfg = MagicMock()
    cfg.get.return_value = {"Authorization": "Bearer x"}
    enriched = enrich_mcp_server(server, config=cfg)
    assert enriched.headers_configured is True
    assert enriched.header_names == ["Authorization"]


def test_resolve_auth_headers_api_key(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("agent.config.CONFIG_DIR", tmp_path / "cfg")
    monkeypatch.setattr("agent.config.CONFIG_FILE", tmp_path / "cfg" / "config.json")
    (tmp_path / "cfg").mkdir(parents=True, exist_ok=True)
    cfg = Config({})
    cfg.set("mcp.tamarind_api_key", "tam-key")
    cfg.save()

    entry = get_catalog_entry("tamarind")
    assert entry is not None
    headers = resolve_auth_headers(entry, Config.load())
    assert headers == {"x-api-key": "tam-key"}
    assert credentials_configured(entry, Config.load()) is True
    assert auth_method_in_use(entry, Config.load()) == "api_key"


def test_resolve_auth_headers_oauth_token(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("agent.config.CONFIG_DIR", tmp_path / "cfg")
    monkeypatch.setattr("agent.config.CONFIG_FILE", tmp_path / "cfg" / "config.json")
    (tmp_path / "cfg").mkdir(parents=True, exist_ok=True)
    cfg = Config({})
    cfg.set("mcp.latch_access_token", "oauth-access")
    cfg.save()

    entry = get_catalog_entry("latch")
    assert entry is not None
    headers = resolve_auth_headers(entry, Config.load())
    assert headers == {"Authorization": "Bearer oauth-access"}
    assert auth_method_in_use(entry, Config.load()) == "oauth"


def test_tool_count_and_status_message_roundtrip(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("agent.config.CONFIG_DIR", tmp_path / "cfg")
    monkeypatch.setattr("agent.config.CONFIG_FILE", tmp_path / "cfg" / "config.json")
    (tmp_path / "cfg").mkdir(parents=True, exist_ok=True)
    Config({}).save()

    save_tool_count("tamarind", 12)
    assert read_tool_count("tamarind") == 12

    save_status_message("tamarind", "Connected")
    assert read_status_message("tamarind") == "Connected"

    clear_health_cache("tamarind")
    assert read_tool_count("tamarind") is None
    assert read_status_message("tamarind") is None

    clear_tool_count("tamarind")


def test_parse_sse_or_json():
    assert parse_sse_or_json('{"jsonrpc":"2.0","id":1}') == [{"jsonrpc": "2.0", "id": 1}]
    raw = 'data: {"a": 1}\n\ndata: {"b": 2}\n'
    parsed = parse_sse_or_json(raw)
    assert parsed == [{"a": 1}, {"b": 2}]
    assert parse_sse_or_json("not valid") == []


def test_probe_mcp_server_success(monkeypatch):
    responses = [
        (200, {"mcp-session-id": "sess-1"}, '{"result":{"serverInfo":{"name":"x"}}}'),
        (200, {}, ""),
        (
            200,
            {},
            'data: {"result":{"tools":[{"name":"tool_a"},{"name":"tool_b"}]}}\n',
        ),
    ]

    def fake_request(body, session=None):
        return responses.pop(0)

    monkeypatch.setattr(
        "agent_server.mcp_service.McpService",
        McpService,
    )
    with patch("agent_server.mcp_service.urllib.request.urlopen") as urlopen:
        # probe_mcp_server uses nested request(); patch at module level
        pass

    # Patch via replacing the inner request by mocking urlopen on HTTPError path
    call_idx = {"n": 0}

    class FakeResp:
        def __init__(self, status, headers, body):
            self.status = status
            self.headers = headers
            self._body = body

        def read(self):
            return self._body.encode()

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    seq = [
        FakeResp(200, {"mcp-session-id": "s1"}, "{}"),
        FakeResp(200, {}, ""),
        FakeResp(
            200,
            {},
            'data: {"result":{"tools":[{"name":"a"}]}}\n',
        ),
    ]

    def fake_urlopen(req, timeout=None):
        return seq.pop(0)

    monkeypatch.setattr("agent_server.mcp_service.urllib.request.urlopen", fake_urlopen)
    result = __import__("agent_server.mcp_service", fromlist=["probe_mcp_server"]).probe_mcp_server(
        url="https://mcp.example.com",
        headers={"Authorization": "Bearer x"},
    )
    assert result["ok"] is True
    assert result["toolCount"] == 1


def test_mcp_service_catalog_statuses(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("agent.config.CONFIG_DIR", tmp_path / "cfg")
    monkeypatch.setattr("agent.config.CONFIG_FILE", tmp_path / "cfg" / "config.json")
    (tmp_path / "cfg").mkdir(parents=True, exist_ok=True)
    Config({}).save()

    store = AgentStore(tmp_path / "agent.db")
    svc = McpService(store)
    statuses = svc.catalog_statuses()
    assert len(statuses) >= 3
    ids = {item["id"] for item in statuses}
    assert "tamarind" in ids


def test_mcp_service_ensure_and_disconnect(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("agent.config.CONFIG_DIR", tmp_path / "cfg")
    monkeypatch.setattr("agent.config.CONFIG_FILE", tmp_path / "cfg" / "config.json")
    (tmp_path / "cfg").mkdir(parents=True, exist_ok=True)
    cfg = Config({})
    cfg.set("mcp.tamarind_api_key", "key")
    cfg.save()

    store = AgentStore(tmp_path / "agent.db")
    svc = McpService(store)
    server = svc.ensure_catalog_server("tamarind", enabled=True)
    assert server.catalog_id == "tamarind"

    again = svc.ensure_catalog_server("tamarind")
    assert again.id == server.id

    result = svc.disconnect("tamarind")
    assert result["ok"] is True
    assert result["configured"] is False


def test_mcp_service_connect_with_api_key(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("agent.config.CONFIG_DIR", tmp_path / "cfg")
    monkeypatch.setattr("agent.config.CONFIG_FILE", tmp_path / "cfg" / "config.json")
    (tmp_path / "cfg").mkdir(parents=True, exist_ok=True)
    Config({}).save()

    store = AgentStore(tmp_path / "agent.db")
    svc = McpService(store)

    monkeypatch.setattr(
        "agent_server.mcp_service.probe_mcp_server",
        lambda **kwargs: {
            "ok": True,
            "toolCount": 3,
            "message": "ok",
            "tools": ["a", "b", "c"],
        },
    )
    result = svc.connect_with_api_key("tamarind", "my-api-key")
    assert result["ok"] is True
    assert result["enabled"] is True
    assert read_tool_count("tamarind") == 3


def test_mcp_service_set_enabled_requires_credentials(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("agent.config.CONFIG_DIR", tmp_path / "cfg")
    monkeypatch.setattr("agent.config.CONFIG_FILE", tmp_path / "cfg" / "config.json")
    (tmp_path / "cfg").mkdir(parents=True, exist_ok=True)
    Config({}).save()

    store = AgentStore(tmp_path / "agent.db")
    svc = McpService(store)
    with pytest.raises(ValueError, match="not configured"):
        svc.set_enabled("tamarind", True)


def test_mcp_service_validate_not_configured(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("agent.config.CONFIG_DIR", tmp_path / "cfg")
    monkeypatch.setattr("agent.config.CONFIG_FILE", tmp_path / "cfg" / "config.json")
    (tmp_path / "cfg").mkdir(parents=True, exist_ok=True)
    Config({}).save()

    store = AgentStore(tmp_path / "agent.db")
    svc = McpService(store)
    result = svc.validate(catalog_id="tamarind")
    assert result["ok"] is False
    assert "not configured" in result["message"].lower()


def test_mcp_service_resolve_runtime_servers(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("agent.config.CONFIG_DIR", tmp_path / "cfg")
    monkeypatch.setattr("agent.config.CONFIG_FILE", tmp_path / "cfg" / "config.json")
    (tmp_path / "cfg").mkdir(parents=True, exist_ok=True)
    cfg = Config({})
    cfg.set("mcp.tamarind_api_key", "k")
    cfg.save()

    store = AgentStore(tmp_path / "agent.db")
    server = store.create_mcp_server(
        name="Tamarind",
        transport="streamable_http",
        command=None,
        args=[],
        url="https://mcp.tamarind.bio",
        enabled=True,
        catalog_id="tamarind",
    )
    svc = McpService(store)
    resolved = svc.resolve_runtime_servers()
    assert len(resolved) == 1
    assert resolved[0]["id"] == server.id
    assert "headers" in resolved[0]
    assert "header_names" not in resolved[0]
