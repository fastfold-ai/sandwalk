"""Unit tests for agent_server.mcp_service helpers and McpService."""

from __future__ import annotations

import json
import urllib.error
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
    oauth_reconnect_required,
    parse_sse_or_json,
    read_status_message,
    read_tool_count,
    resolve_auth_headers,
    save_status_message,
    save_tool_count,
    set_custom_headers,
)
from agent_server.store import AgentStore


def test_paperclip_catalog_entry_featured_over_linear():
    from agent.mcp_catalog import MCP_CATALOG, get_catalog_entry

    paperclip = get_catalog_entry("paperclip")
    linear = get_catalog_entry("linear")
    huggingface = get_catalog_entry("huggingface")
    tavily = get_catalog_entry("tavily")
    assert paperclip is not None
    assert linear is not None
    assert huggingface is not None
    assert paperclip.featured is True
    assert huggingface.featured is True
    assert linear.featured is False
    assert paperclip.auth_mode == "api_key_or_oauth"
    assert paperclip.preferred_auth == "oauth"
    assert paperclip.url == "https://paperclip.gxl.ai/mcp"
    assert paperclip.api_key_header == "X-API-Key"
    assert paperclip.api_key_config_key == "mcp.paperclip_api_key"
    assert huggingface.url == "https://huggingface.co/mcp"
    assert huggingface.auth_mode == "api_key"
    assert huggingface.api_key_env_var == "HF_TOKEN"
    assert huggingface.api_key_header_prefix == "Bearer "
    assert tavily is not None
    assert tavily.featured is True
    assert tavily.auth_mode == "api_key_or_oauth"
    assert tavily.preferred_auth == "oauth"
    assert tavily.api_key_config_key == "api.tavily_api_key"
    assert tavily.api_key_header == "Authorization"
    assert tavily.api_key_header_prefix == "Bearer "
    assert {e.id for e in MCP_CATALOG} >= {
        "tamarind",
        "latch",
        "neurosnap",
        "paperclip",
        "huggingface",
        "tavily",
        "linear",
    }
    assert "betterstack" not in {e.id for e in MCP_CATALOG}


def test_resource_metadata_url_from_www_authenticate():
    from agent_server.mcp_service import _resource_metadata_url_from_www_authenticate

    assert (
        _resource_metadata_url_from_www_authenticate(
            'Bearer realm="mcp", resource_metadata="https://mcp.betterstack.com/.well-known/oauth-protected-resource"'
        )
        == "https://mcp.betterstack.com/.well-known/oauth-protected-resource"
    )
    assert _resource_metadata_url_from_www_authenticate(None) is None
    assert _resource_metadata_url_from_www_authenticate('Bearer realm="mcp"') is None


def test_ensure_mcp_http_headers_adds_user_agent():
    from agent_server.mcp_service import MCP_HTTP_USER_AGENT, ensure_mcp_http_headers

    assert ensure_mcp_http_headers(None)["User-Agent"] == MCP_HTTP_USER_AGENT
    assert ensure_mcp_http_headers({})["User-Agent"] == MCP_HTTP_USER_AGENT
    with_auth = ensure_mcp_http_headers({"Authorization": "Bearer x"})
    assert with_auth["Authorization"] == "Bearer x"
    assert with_auth["User-Agent"] == MCP_HTTP_USER_AGENT
    custom = ensure_mcp_http_headers({"User-Agent": "CustomAgent/1"})
    assert custom["User-Agent"] == "CustomAgent/1"


def test_http_json_sends_user_agent(monkeypatch):
    from agent_server import mcp_service as mod

    captured: dict[str, str] = {}

    class FakeResp:
        status = 200

        def read(self):
            return b'{"ok":true}'

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    def fake_urlopen(req, timeout=None):
        captured["ua"] = req.get_header("User-agent")
        return FakeResp()

    monkeypatch.setattr(mod.urllib.request, "urlopen", fake_urlopen)
    status, data = mod._http_json("https://example.com/.well-known/oauth-protected-resource")
    assert status == 200
    assert data == {"ok": True}
    assert captured["ua"]
    assert "Sandwalk" in captured["ua"]
    assert "Python-urllib" not in captured["ua"]


def test_probe_mcp_server_sends_user_agent(monkeypatch):
    from agent_server import mcp_service as mod

    seen: list[str] = []

    class Err(urllib.error.HTTPError):
        def __init__(self, req):
            super().__init__(req.full_url, 401, "Unauthorized", hdrs={}, fp=None)

        def read(self):
            return b'{"error":"unauthorized"}'

    def fake_urlopen(req, timeout=None):
        seen.append(req.get_header("User-agent") or "")
        raise Err(req)

    monkeypatch.setattr(mod.urllib.request, "urlopen", fake_urlopen)
    result = mod.probe_mcp_server(url="https://mcp.betterstack.com")
    assert result["ok"] is False
    assert seen
    assert all("Sandwalk" in ua for ua in seen)
    assert "401" in result["message"]


def test_discover_oauth_for_url_betterstack_shape(monkeypatch):
    from agent_server import mcp_service as mod

    responses = {
        "https://mcp.betterstack.com/.well-known/oauth-protected-resource": (
            200,
            {
                "resource": "https://mcp.betterstack.com",
                "authorization_servers": ["https://betterstack.com"],
                "scopes_supported": ["read", "write"],
            },
        ),
        "https://betterstack.com/.well-known/oauth-authorization-server": (
            200,
            {
                "issuer": "https://betterstack.com",
                "authorization_endpoint": "https://betterstack.com/oauth/authorize",
                "token_endpoint": "https://betterstack.com/oauth/token",
                "registration_endpoint": "https://betterstack.com/oauth/register",
            },
        ),
    }

    monkeypatch.setattr(mod, "_probe_resource_metadata_url", lambda url: None)

    def fake_http_json(url, **kwargs):
        if url in responses:
            return responses[url]
        return 404, {}

    monkeypatch.setattr(mod, "_http_json", fake_http_json)
    meta = mod.discover_oauth_for_url("https://mcp.betterstack.com", label="betterstack")
    assert meta["authorization_endpoint"] == "https://betterstack.com/oauth/authorize"
    assert meta["registration_endpoint"] == "https://betterstack.com/oauth/register"
    assert meta["scopes"] == ["read", "write"]
    assert meta["resource"] == "https://mcp.betterstack.com"


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
    server.catalog_id = None
    server.transport = "streamable_http"
    server.enabled = True
    server.headers_helper_command = None
    server.model_copy = lambda update: MagicMock(
        **{**{k: getattr(server, k) for k in ("id", "catalog_id", "transport", "enabled", "headers_helper_command")}, **update}
    )
    cfg = MagicMock()

    def _get(key, default=None):
        if key == "mcp.custom_s1_headers":
            return {"Authorization": "Bearer x"}
        return default

    cfg.get.side_effect = _get
    enriched = enrich_mcp_server(server, config=cfg)
    assert enriched.headers_configured is True
    assert enriched.header_names == ["Authorization"]


def test_enrich_mcp_server_forces_unauthenticated_remote_off():
    server = MagicMock()
    server.id = "s2"
    server.catalog_id = None
    server.transport = "streamable_http"
    server.enabled = True
    server.headers_helper_command = None
    captured = {}

    def _copy(update):
        captured.update(update)
        return MagicMock(**{**server.__dict__, **update})

    server.model_copy = _copy
    cfg = MagicMock()
    cfg.get.return_value = None
    enrich_mcp_server(server, config=cfg)
    assert captured.get("enabled") is False
    assert captured.get("headers_configured") is False


def test_resolve_auth_headers_api_key(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("agent.config.CONFIG_DIR", tmp_path / "cfg")
    monkeypatch.setattr("agent.config.CONFIG_FILE", tmp_path / "cfg" / "config.json")
    (tmp_path / "cfg").mkdir(parents=True, exist_ok=True)
    cfg = Config({})
    cfg.set("mcp.tamarind_api_key", "tam-key")
    cfg.set("api.tavily_api_key", "tvly-key")
    cfg.save()

    entry = get_catalog_entry("tamarind")
    assert entry is not None
    headers = resolve_auth_headers(entry, Config.load())
    assert headers is not None
    assert headers.get("x-api-key") == "tam-key"
    assert "Sandwalk" in (headers.get("User-Agent") or "")
    assert credentials_configured(entry, Config.load()) is True
    assert auth_method_in_use(entry, Config.load()) == "api_key"

    tavily = get_catalog_entry("tavily")
    assert tavily is not None
    tavily_headers = resolve_auth_headers(tavily, Config.load())
    assert tavily_headers is not None
    assert tavily_headers.get("Authorization") == "Bearer tvly-key"


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
    assert headers is not None
    assert headers.get("Authorization") == "Bearer oauth-access"
    assert "Sandwalk" in (headers.get("User-Agent") or "")
    assert auth_method_in_use(entry, Config.load()) == "oauth"


def test_oauth_reconnect_required_when_expired_without_refresh(
    tmp_path: Path, monkeypatch
):
    monkeypatch.setattr("agent.config.CONFIG_DIR", tmp_path / "cfg")
    monkeypatch.setattr("agent.config.CONFIG_FILE", tmp_path / "cfg" / "config.json")
    (tmp_path / "cfg").mkdir(parents=True, exist_ok=True)
    cfg = Config({})
    cfg.set("mcp.latch_access_token", "oauth-access")
    cfg.set("mcp.latch_token_expires_at", "1")  # far in the past
    cfg.save()

    entry = get_catalog_entry("latch")
    assert entry is not None
    message = oauth_reconnect_required(entry, Config.load())
    assert message is not None
    assert "expired" in message.lower()


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
    assert "paperclip" in ids
    by_id = {item["id"]: item for item in statuses}
    assert by_id["paperclip"]["featured"] is True
    assert by_id["linear"]["featured"] is False
    assert by_id["paperclip"]["auth_mode"] == "api_key_or_oauth"


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
    # API-key Connect must not auto-enable — toggle is UI/CLI only.
    assert result["enabled"] is False
    assert read_tool_count("tamarind") == 3

    enabled = svc.set_enabled("tamarind", True)
    assert enabled["ok"] is True
    assert enabled["enabled"] is True


def test_complete_oauth_enables_catalog_on_success(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("agent.config.CONFIG_DIR", tmp_path / "cfg")
    monkeypatch.setattr("agent.config.CONFIG_FILE", tmp_path / "cfg" / "config.json")
    (tmp_path / "cfg").mkdir(parents=True, exist_ok=True)
    Config({}).save()

    store = AgentStore(tmp_path / "agent.db")
    svc = McpService(store)

    from agent_server import mcp_service as mod

    state = "oauth-state-1"
    with mod._oauth_lock:
        mod._oauth_states[state] = {
            "catalog_id": "latch",
            "verifier": "v",
            "redirect_uri": "http://127.0.0.1/callback",
            "client_id": "cid",
            "client_secret": None,
            "token_endpoint": "https://example.com/token",
            "resource": "https://mcp.latch.bio/mcp",
            "created_at": 0,
        }

    monkeypatch.setattr(
        mod,
        "_http_json",
        lambda *a, **k: (200, {"access_token": "tok", "expires_in": 3600}),
    )
    monkeypatch.setattr(
        mod,
        "probe_mcp_server",
        lambda **kwargs: {
            "ok": True,
            "toolCount": 2,
            "message": "Connected — 2 tools available",
            "tools": ["a", "b"],
            "toolDetails": [],
        },
    )

    result = svc.complete_oauth(code="abc", state=state)
    assert result["ok"] is True
    assert result["enabled"] is True
    assert result["catalogId"] == "latch"
    server = next(s for s in store.list_mcp_servers() if s.catalog_id == "latch")
    assert server.enabled is True


def test_complete_oauth_enables_custom_on_success(tmp_path: Path, monkeypatch):
    monkeypatch.setattr("agent.config.CONFIG_DIR", tmp_path / "cfg")
    monkeypatch.setattr("agent.config.CONFIG_FILE", tmp_path / "cfg" / "config.json")
    (tmp_path / "cfg").mkdir(parents=True, exist_ok=True)
    Config({}).save()

    store = AgentStore(tmp_path / "agent.db")
    server = store.create_mcp_server(
        name="betterstack",
        transport="streamable_http",
        command=None,
        args=[],
        url="https://mcp.betterstack.com",
        enabled=False,
    )
    svc = McpService(store)

    from agent_server import mcp_service as mod

    state = "oauth-state-custom"
    with mod._oauth_lock:
        mod._oauth_states[state] = {
            "server_id": server.id,
            "mcp_url": "https://mcp.betterstack.com",
            "verifier": "v",
            "redirect_uri": "http://127.0.0.1/callback",
            "client_id": "cid",
            "client_secret": None,
            "token_endpoint": "https://betterstack.com/oauth/token",
            "resource": "https://mcp.betterstack.com",
            "created_at": 0,
        }

    monkeypatch.setattr(
        mod,
        "_http_json",
        lambda *a, **k: (200, {"access_token": "tok", "refresh_token": "rt"}),
    )
    monkeypatch.setattr(
        mod,
        "probe_mcp_server",
        lambda **kwargs: {
            "ok": True,
            "toolCount": 5,
            "message": "Connected — 5 tools available",
            "tools": ["t1"],
            "toolDetails": [],
        },
    )

    result = svc.complete_oauth(code="abc", state=state)
    assert result["ok"] is True
    assert result["enabled"] is True
    assert result["serverId"] == server.id
    updated = next(s for s in store.list_mcp_servers() if s.id == server.id)
    assert updated.enabled is True


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
