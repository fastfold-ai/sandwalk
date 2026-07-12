"""MCP catalog connect, credential resolution, OAuth, and probe helpers."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import secrets
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from base64 import urlsafe_b64encode
from dataclasses import dataclass, field
from typing import Any

from agent.config import Config
from agent.mcp_catalog import MCP_CATALOG, McpCatalogEntry, get_catalog_entry
from agent_server.store import AgentStore

logger = logging.getLogger("mcp_service")

# In-memory OAuth PKCE state (local agent server only).
_oauth_states: dict[str, dict[str, Any]] = {}
_oauth_lock = threading.Lock()

_HEADERS_HELPER_TIMEOUT_S = 10


def custom_headers_config_key(server_id: str) -> str:
    return f"mcp.custom_{server_id}_headers"


def get_custom_headers(config: Config | None, server_id: str) -> dict[str, str]:
    cfg = config or Config.load()
    raw = cfg.get(custom_headers_config_key(server_id))
    if isinstance(raw, dict):
        return {
            str(key).strip(): str(value)
            for key, value in raw.items()
            if str(key).strip() and str(value)
        }
    if isinstance(raw, str) and raw.strip():
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return {}
        if isinstance(parsed, dict):
            return {
                str(key).strip(): str(value)
                for key, value in parsed.items()
                if str(key).strip() and str(value)
            }
    return {}


def set_custom_headers(
    server_id: str,
    headers: dict[str, str] | None,
    *,
    config: Config | None = None,
) -> None:
    cfg = config or Config.load()
    key = custom_headers_config_key(server_id)
    cleaned = {
        str(name).strip(): str(value)
        for name, value in (headers or {}).items()
        if str(name).strip() and str(value)
    }
    if cleaned:
        cfg.set(key, cleaned)
    else:
        cfg.unset(key)
    cfg.save()


def clear_custom_headers(server_id: str, *, config: Config | None = None) -> None:
    set_custom_headers(server_id, None, config=config)


def enrich_mcp_server(server, *, config: Config | None = None):
    """Attach non-secret header metadata to an MCP server model."""
    headers = get_custom_headers(config, server.id)
    names = sorted(headers.keys())
    return server.model_copy(
        update={
            "header_names": names,
            "headers_configured": bool(names),
        }
    )


def run_headers_helper_command(command: str) -> dict[str, str] | None:
    """Run a shell command that prints a JSON object of HTTP headers on stdout."""
    import subprocess

    try:
        completed = subprocess.run(
            command,
            shell=True,
            check=False,
            capture_output=True,
            text=True,
            timeout=_HEADERS_HELPER_TIMEOUT_S,
        )
    except subprocess.TimeoutExpired:
        logger.warning("MCP headers helper timed out after %ss", _HEADERS_HELPER_TIMEOUT_S)
        return None
    except OSError as exc:
        logger.warning("MCP headers helper failed to start: %s", exc)
        return None

    if completed.returncode != 0:
        stderr = (completed.stderr or "").strip()
        logger.warning(
            "MCP headers helper exited %s: %s",
            completed.returncode,
            stderr[:300] or "(no stderr)",
        )
        return None

    stdout = (completed.stdout or "").strip()
    if not stdout:
        return None
    try:
        parsed = json.loads(stdout)
    except json.JSONDecodeError:
        logger.warning("MCP headers helper stdout was not valid JSON")
        return None
    if not isinstance(parsed, dict):
        logger.warning("MCP headers helper JSON must be an object")
        return None
    return {
        str(key).strip(): str(value)
        for key, value in parsed.items()
        if str(key).strip() and value is not None and str(value)
    }


def resolve_custom_server_headers(server, *, config: Config | None = None) -> dict[str, str] | None:
    """Resolve auth headers for a custom (non-catalog) remote MCP server.

    Precedence: headers helper command (if set and succeeds) → static custom headers.
    """
    helper = getattr(server, "headers_helper_command", None)
    if helper and str(helper).strip():
        dynamic = run_headers_helper_command(str(helper).strip())
        if dynamic:
            return dynamic
    static = get_custom_headers(config, server.id)
    return static or None


def _cfg_secret(config: Config, config_key: str | None, env_var: str | None) -> str | None:
    if env_var:
        env_value = str(os.environ.get(env_var) or "").strip()
        if env_value:
            return env_value
    if config_key:
        value = str(config.get(config_key) or "").strip()
        if value:
            return value
    return None


def resolve_auth_headers(
    entry: McpCatalogEntry,
    config: Config | None = None,
) -> dict[str, str] | None:
    """Build HTTP headers for a catalog MCP from keys (/keys) or OAuth tokens."""
    cfg = config or Config.load()

    # API-key-only entries should never prefer a stale OAuth token.
    if entry.auth_mode != "api_key":
        access = _cfg_secret(cfg, f"mcp.{entry.id}_access_token", None)
        if access:
            return {"Authorization": f"Bearer {access}"}

    if entry.api_key_config_key and entry.api_key_header:
        api_key = _cfg_secret(cfg, entry.api_key_config_key, entry.api_key_env_var)
        if api_key:
            prefix = entry.api_key_header_prefix or ""
            return {entry.api_key_header: f"{prefix}{api_key}"}
    return None


def credentials_configured(entry: McpCatalogEntry, config: Config | None = None) -> bool:
    return resolve_auth_headers(entry, config) is not None


def auth_method_in_use(entry: McpCatalogEntry, config: Config | None = None) -> str | None:
    cfg = config or Config.load()
    if _cfg_secret(cfg, f"mcp.{entry.id}_access_token", None):
        return "oauth"
    if entry.api_key_config_key and _cfg_secret(
        cfg, entry.api_key_config_key, entry.api_key_env_var
    ):
        return "api_key"
    return None


def _tool_count_key(catalog_id: str) -> str:
    return f"mcp.{catalog_id}_tool_count"


def _status_message_key(catalog_id: str) -> str:
    return f"mcp.{catalog_id}_status_message"


def read_tool_count(catalog_id: str, config: Config | None = None) -> int | None:
    cfg = config or Config.load()
    raw = cfg.get(_tool_count_key(catalog_id))
    if raw is None or raw == "":
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def save_tool_count(catalog_id: str, tool_count: int) -> None:
    cfg = Config.load()
    cfg.set(_tool_count_key(catalog_id), int(tool_count))
    if cfg.get(_status_message_key(catalog_id)) is not None:
        cfg.unset(_status_message_key(catalog_id))
    cfg.save()


def clear_tool_count(catalog_id: str, config: Config | None = None) -> None:
    cfg = config or Config.load()
    key = _tool_count_key(catalog_id)
    changed = False
    if cfg.get(key) is not None:
        cfg.unset(key)
        changed = True
    if changed:
        cfg.save()


def read_status_message(catalog_id: str, config: Config | None = None) -> str | None:
    cfg = config or Config.load()
    raw = cfg.get(_status_message_key(catalog_id))
    if raw is None or raw == "":
        return None
    return str(raw)


def save_status_message(catalog_id: str, message: str | None) -> None:
    cfg = Config.load()
    key = _status_message_key(catalog_id)
    if message:
        cfg.set(key, str(message)[:500])
    elif cfg.get(key) is not None:
        cfg.unset(key)
    cfg.save()


def clear_health_cache(catalog_id: str, config: Config | None = None) -> None:
    cfg = config or Config.load()
    changed = False
    for key in (_tool_count_key(catalog_id), _status_message_key(catalog_id)):
        if cfg.get(key) is not None:
            cfg.unset(key)
            changed = True
    if changed:
        cfg.save()


def parse_sse_or_json(raw: str) -> list[dict[str, Any]]:
    msgs: list[dict[str, Any]] = []
    stripped = raw.strip()
    if stripped.startswith("{"):
        try:
            msgs.append(json.loads(stripped))
            return msgs
        except json.JSONDecodeError:
            pass
    for line in raw.splitlines():
        if line.startswith("data:"):
            payload = line[5:].strip()
            if not payload:
                continue
            try:
                msgs.append(json.loads(payload))
            except json.JSONDecodeError:
                continue
    return msgs


def probe_mcp_server(
    *,
    url: str,
    headers: dict[str, str] | None = None,
    timeout: float = 45.0,
) -> dict[str, Any]:
    """MCP initialize + tools/list smoke test. Returns ok/toolCount/message/tools."""

    def request(body: dict[str, Any], session: str | None = None) -> tuple[int, dict[str, str], str]:
        req_headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            **(headers or {}),
        }
        if session:
            req_headers["mcp-session-id"] = session
        data = json.dumps(body).encode()
        req = urllib.request.Request(url, data=data, headers=req_headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return (
                    resp.status,
                    {k.lower(): v for k, v in resp.headers.items()},
                    resp.read().decode(),
                )
        except urllib.error.HTTPError as exc:
            return (
                exc.code,
                {k.lower(): v for k, v in exc.headers.items()},
                exc.read().decode(),
            )

    init_body = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "fastfold-mcp", "version": "0.1.0"},
        },
    }
    status, resp_headers, raw = request(init_body)
    if status >= 400:
        return {
            "ok": False,
            "toolCount": 0,
            "message": f"initialize failed HTTP {status}: {raw[:300]}",
            "tools": [],
        }
    session = resp_headers.get("mcp-session-id")
    request({"jsonrpc": "2.0", "method": "notifications/initialized"}, session)
    status2, _, raw2 = request(
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
        session,
    )
    msgs = parse_sse_or_json(raw2)
    if status2 >= 400 or not msgs:
        return {
            "ok": False,
            "toolCount": 0,
            "message": f"tools/list failed HTTP {status2}: {raw2[:300]}",
            "tools": [],
        }
    msg = msgs[0]
    if "error" in msg:
        err = msg["error"]
        detail = err.get("message") if isinstance(err, dict) else str(err)
        return {"ok": False, "toolCount": 0, "message": str(detail), "tools": []}
    tools = (msg.get("result") or {}).get("tools") or []
    names = [str(t.get("name") or "") for t in tools if isinstance(t, dict)]
    return {
        "ok": True,
        "toolCount": len(tools),
        "message": f"Connected — {len(tools)} tools available",
        "tools": names[:50],
        "serverInfo": (parse_sse_or_json(raw)[0].get("result") or {}).get("serverInfo")
        if parse_sse_or_json(raw)
        else None,
    }


def _pkce_pair() -> tuple[str, str]:
    verifier = urlsafe_b64encode(secrets.token_bytes(32)).rstrip(b"=").decode()
    challenge = urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    return verifier, challenge


def _http_json(
    url: str,
    *,
    method: str = "GET",
    body: dict[str, Any] | bytes | None = None,
    headers: dict[str, str] | None = None,
    form: dict[str, str] | None = None,
) -> tuple[int, Any]:
    data: bytes | None = None
    req_headers = {"Accept": "application/json", **(headers or {})}
    if form is not None:
        data = urllib.parse.urlencode(form).encode()
        req_headers["Content-Type"] = "application/x-www-form-urlencoded"
    elif isinstance(body, dict):
        data = json.dumps(body).encode()
        req_headers["Content-Type"] = "application/json"
    elif isinstance(body, (bytes, bytearray)):
        data = bytes(body)
    req = urllib.request.Request(url, data=data, headers=req_headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode()
            try:
                return resp.status, json.loads(raw) if raw else {}
            except json.JSONDecodeError:
                return resp.status, raw
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode()
        try:
            return exc.code, json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            return exc.code, raw


def discover_oauth(entry: McpCatalogEntry) -> dict[str, Any]:
    """Fetch OAuth protected-resource + authorization-server metadata."""
    candidates = [
        f"{urllib.parse.urlparse(entry.url).scheme}://{urllib.parse.urlparse(entry.url).netloc}/.well-known/oauth-protected-resource",
        f"{urllib.parse.urlparse(entry.url).scheme}://{urllib.parse.urlparse(entry.url).netloc}/.well-known/oauth-protected-resource/mcp",
        entry.url.rstrip("/") + "/.well-known/oauth-protected-resource",
    ]
    # Known overrides from smoke tests
    if entry.id == "latch":
        candidates.insert(0, "https://mcp.latch.bio/.well-known/oauth-protected-resource/mcp")
    if entry.id == "linear":
        candidates.insert(0, "https://mcp.linear.app/.well-known/oauth-protected-resource/mcp")

    resource_meta: dict[str, Any] | None = None
    for url in candidates:
        status, data = _http_json(url)
        if status == 200 and isinstance(data, dict) and data.get("authorization_servers"):
            resource_meta = data
            break
    if not resource_meta:
        raise ValueError(f"Could not discover OAuth resource metadata for {entry.id}")

    as_list = [str(item).rstrip("/") for item in (resource_meta.get("authorization_servers") or [])]
    if not as_list:
        raise ValueError(f"No authorization servers listed for {entry.id}")

    # Prefer an AS that advertises dynamic client registration when available.
    discovered: list[dict[str, Any]] = []
    for issuer in as_list:
        as_meta_urls = [
            f"{issuer}/.well-known/oauth-authorization-server",
            f"{issuer}/.well-known/openid-configuration",
        ]
        # Linear hosts AS metadata on mcp.linear.app
        if entry.id == "linear":
            as_meta_urls.insert(
                0, "https://mcp.linear.app/.well-known/oauth-authorization-server"
            )
        for url in as_meta_urls:
            status, data = _http_json(url)
            if status == 200 and isinstance(data, dict) and data.get("authorization_endpoint"):
                discovered.append(
                    {
                        "issuer": data.get("issuer") or issuer,
                        "authorization_endpoint": data["authorization_endpoint"],
                        "token_endpoint": data["token_endpoint"],
                        "registration_endpoint": data.get("registration_endpoint"),
                    }
                )
                break

    if not discovered:
        raise ValueError(f"Could not discover OAuth authorization server for {entry.id}")

    as_meta = next((row for row in discovered if row.get("registration_endpoint")), discovered[0])

    return {
        "resource": resource_meta.get("resource") or entry.url,
        "scopes": resource_meta.get("scopes_supported") or ["openid", "offline_access"],
        "authorization_endpoint": as_meta["authorization_endpoint"],
        "token_endpoint": as_meta["token_endpoint"],
        "registration_endpoint": as_meta.get("registration_endpoint"),
        "issuer": as_meta.get("issuer"),
    }


@dataclass
class McpService:
    store: AgentStore
    public_base_url: str = "http://127.0.0.1:8787"
    _lock: threading.RLock = field(default_factory=threading.RLock)

    def catalog_statuses(self) -> list[dict[str, Any]]:
        """Fast catalog list — uses cached health from connect/enable/doctor.

        Live probes belong in doctor / connect / enable, not on every dashboard load.
        """
        cfg = Config.load()
        servers = self.store.list_mcp_servers()
        by_catalog = {
            s.catalog_id: s for s in servers if getattr(s, "catalog_id", None)
        }
        out: list[dict[str, Any]] = []
        for entry in MCP_CATALOG:
            server = by_catalog.get(entry.id)
            configured = credentials_configured(entry, cfg)
            enabled = bool(server.enabled) if server else False
            tool_count = read_tool_count(entry.id, cfg)
            status_message = read_status_message(entry.id, cfg)
            connected = False

            if enabled:
                if not configured:
                    status_message = "Enabled but not authenticated"
                    tool_count = None
                elif tool_count is not None and not status_message:
                    connected = True
                elif status_message:
                    connected = False
                else:
                    # Enabled + configured, but not probed yet.
                    status_message = None
            else:
                # Disabled cards should not show stale probe errors.
                status_message = None

            out.append(
                {
                    "id": entry.id,
                    "name": entry.name,
                    "description": entry.description,
                    "url": entry.url,
                    "transport": entry.transport,
                    "auth_mode": entry.auth_mode,
                    "preferred_auth": entry.preferred_auth,
                    "api_key_env_var": entry.api_key_env_var,
                    "docs_url": entry.docs_url,
                    "setup_url": entry.setup_url,
                    "integration_key": entry.integration_key,
                    "default_enabled": False,
                    "configured": configured,
                    "auth_method": auth_method_in_use(entry, cfg),
                    "enabled": enabled,
                    "server_id": server.id if server else None,
                    "connected": connected,
                    "tool_count": tool_count if enabled else None,
                    "status_message": status_message,
                }
            )
        return out

    def ensure_catalog_server(self, catalog_id: str, *, enabled: bool = False):
        entry = get_catalog_entry(catalog_id)
        if entry is None:
            raise KeyError(catalog_id)
        existing = next(
            (
                s
                for s in self.store.list_mcp_servers()
                if getattr(s, "catalog_id", None) == catalog_id
            ),
            None,
        )
        if existing:
            return existing
        return self.store.create_mcp_server(
            name=entry.name,
            transport=entry.transport,
            command=None,
            args=[],
            url=entry.url,
            enabled=enabled,
            catalog_id=entry.id,
        )

    def save_api_key(self, catalog_id: str, api_key: str) -> None:
        entry = get_catalog_entry(catalog_id)
        if entry is None or not entry.api_key_config_key:
            raise ValueError(f"{catalog_id} does not support API key auth")
        key = api_key.strip()
        if not key:
            raise ValueError("API key is required")
        cfg = Config.load()
        # Drop stale OAuth tokens so the new API key is what runtime/doctor use.
        for oauth_key in (
            f"mcp.{catalog_id}_access_token",
            f"mcp.{catalog_id}_refresh_token",
            f"mcp.{catalog_id}_token_expires_at",
            f"mcp.{catalog_id}_client_id",
            f"mcp.{catalog_id}_client_secret",
        ):
            if cfg.get(oauth_key) is not None:
                cfg.unset(oauth_key)
        cfg.set(entry.api_key_config_key, key)
        cfg.save()

    def clear_credentials(self, catalog_id: str) -> None:
        entry = get_catalog_entry(catalog_id)
        if entry is None:
            raise KeyError(catalog_id)
        cfg = Config.load()
        keys = [
            f"mcp.{catalog_id}_access_token",
            f"mcp.{catalog_id}_refresh_token",
            f"mcp.{catalog_id}_token_expires_at",
            f"mcp.{catalog_id}_client_id",
            f"mcp.{catalog_id}_client_secret",
        ]
        if entry.api_key_config_key:
            keys.append(entry.api_key_config_key)
        keys.append(_tool_count_key(catalog_id))
        keys.append(_status_message_key(catalog_id))
        for key in keys:
            if cfg.get(key) is not None:
                cfg.unset(key)
        cfg.save()

    def connect_with_api_key(self, catalog_id: str, api_key: str) -> dict[str, Any]:
        entry = get_catalog_entry(catalog_id)
        if entry is None:
            raise KeyError(catalog_id)
        if entry.auth_mode == "oauth":
            raise ValueError(f"{entry.name} requires OAuth browser connect")
        key = api_key.strip()
        if not key:
            raise ValueError("API key is required")
        if not entry.api_key_header:
            raise ValueError(f"{entry.name} has no API key header configured")

        # Persist the new key first so Reconnect always updates Integrations/keys.
        self.save_api_key(catalog_id, key)

        prefix = entry.api_key_header_prefix or ""
        header_candidates: list[dict[str, str]] = [
            {entry.api_key_header: f"{prefix}{key}"},
        ]
        # Neurosnap accepts Bearer or X-API-KEY; try the alternate if primary fails.
        if entry.id == "neurosnap":
            header_candidates.append({"X-API-KEY": key})
            header_candidates.append({"Authorization": f"Bearer {key}"})

        result: dict[str, Any] | None = None
        seen: set[str] = set()
        for headers in header_candidates:
            sig = json.dumps(headers, sort_keys=True)
            if sig in seen:
                continue
            seen.add(sig)
            result = probe_mcp_server(url=entry.url, headers=headers)
            if result.get("ok"):
                break
        assert result is not None

        if not result["ok"]:
            server = self.ensure_catalog_server(catalog_id, enabled=False)
            if server.enabled:
                server = self.store.update_mcp_server(server.id, enabled=False) or server
            clear_tool_count(catalog_id)
            save_status_message(
                catalog_id, str(result.get("message") or "Connection failed")
            )
            return {
                "ok": False,
                "serverId": server.id,
                "enabled": False,
                **result,
            }

        server = self.ensure_catalog_server(catalog_id, enabled=True)
        if not server.enabled:
            server = self.store.update_mcp_server(server.id, enabled=True) or server
        save_tool_count(catalog_id, int(result.get("toolCount") or 0))
        return {
            "ok": True,
            "serverId": server.id,
            "enabled": True,
            **result,
        }

    def disconnect(self, catalog_id: str) -> dict[str, Any]:
        self.clear_credentials(catalog_id)
        server = next(
            (
                s
                for s in self.store.list_mcp_servers()
                if getattr(s, "catalog_id", None) == catalog_id
            ),
            None,
        )
        if server and server.enabled:
            self.store.update_mcp_server(server.id, enabled=False)
        return {"ok": True, "enabled": False, "configured": False}

    def set_enabled(self, catalog_id: str, enabled: bool) -> dict[str, Any]:
        """Enable/disable a catalog MCP. Enable requires credentials already saved."""
        entry = get_catalog_entry(catalog_id)
        if entry is None:
            raise KeyError(catalog_id)
        if enabled:
            if not credentials_configured(entry):
                raise ValueError(
                    f"{entry.name} is not configured — Connect with OAuth or API key first"
                )
            server = self.ensure_catalog_server(catalog_id, enabled=True)
            if not server.enabled:
                server = self.store.update_mcp_server(server.id, enabled=True) or server
            probe = self.validate(catalog_id=catalog_id)
            if probe.get("ok"):
                tool_count = int(probe.get("toolCount") or 0)
                save_tool_count(catalog_id, tool_count)
                return {
                    "ok": True,
                    "enabled": True,
                    "configured": True,
                    "serverId": server.id,
                    "catalogId": catalog_id,
                    "toolCount": tool_count,
                }
            clear_tool_count(catalog_id)
            save_status_message(
                catalog_id, str(probe.get("message") or "Connection failed")
            )
            return {
                "ok": False,
                "enabled": True,
                "configured": True,
                "serverId": server.id,
                "catalogId": catalog_id,
                "toolCount": None,
                "message": probe.get("message"),
            }
        server = next(
            (
                s
                for s in self.store.list_mcp_servers()
                if getattr(s, "catalog_id", None) == catalog_id
            ),
            None,
        )
        if server and server.enabled:
            server = self.store.update_mcp_server(server.id, enabled=False) or server
        return {
            "ok": True,
            "enabled": False,
            "configured": credentials_configured(entry),
            "serverId": server.id if server else None,
            "catalogId": catalog_id,
        }

    def validate(self, catalog_id: str | None = None, server_id: str | None = None) -> dict[str, Any]:
        cfg = Config.load()
        if catalog_id:
            entry = get_catalog_entry(catalog_id)
            if entry is None:
                raise KeyError(catalog_id)
            headers = resolve_auth_headers(entry, cfg)
            if not headers:
                return {
                    "ok": False,
                    "toolCount": 0,
                    "message": "Not configured — Connect with OAuth or API key first",
                    "tools": [],
                }
            return probe_mcp_server(url=entry.url, headers=headers)

        if server_id:
            server = next(
                (s for s in self.store.list_mcp_servers() if s.id == server_id),
                None,
            )
            if server is None:
                raise KeyError(server_id)
            headers: dict[str, str] | None = None
            if getattr(server, "catalog_id", None):
                entry = get_catalog_entry(server.catalog_id)
                if entry:
                    headers = resolve_auth_headers(entry, cfg)
            else:
                headers = resolve_custom_server_headers(server, config=cfg)
            if not server.url:
                return {
                    "ok": False,
                    "toolCount": 0,
                    "message": "stdio MCP probe not supported in doctor yet",
                    "tools": [],
                }
            return probe_mcp_server(url=server.url, headers=headers)

        raise ValueError("catalog_id or server_id required")

    def start_oauth(self, catalog_id: str) -> dict[str, Any]:
        entry = get_catalog_entry(catalog_id)
        if entry is None:
            raise KeyError(catalog_id)
        if entry.auth_mode == "api_key":
            raise ValueError(f"{entry.name} uses API key auth, not OAuth")

        meta = discover_oauth(entry)
        redirect_uri = f"{self.public_base_url.rstrip('/')}/v1/mcp-servers/oauth/callback"
        verifier, challenge = _pkce_pair()
        state = secrets.token_urlsafe(24)

        client_id: str | None = None
        client_secret: str | None = None
        cfg = Config.load()
        stored_client = str(cfg.get(f"mcp.{catalog_id}_client_id") or "").strip()
        stored_secret = str(cfg.get(f"mcp.{catalog_id}_client_secret") or "").strip() or None

        if stored_client:
            client_id = stored_client
            client_secret = stored_secret
        elif meta.get("registration_endpoint"):
            reg_body = {
                "client_name": "FastFold Agent",
                "redirect_uris": [redirect_uri],
                "grant_types": ["authorization_code", "refresh_token"],
                "response_types": ["code"],
                "token_endpoint_auth_method": "none",
            }
            status, data = _http_json(
                str(meta["registration_endpoint"]),
                method="POST",
                body=reg_body,
            )
            if status >= 400 or not isinstance(data, dict) or not data.get("client_id"):
                raise ValueError(f"OAuth client registration failed: {data}")
            client_id = str(data["client_id"])
            client_secret = str(data["client_secret"]) if data.get("client_secret") else None
            cfg.set(f"mcp.{catalog_id}_client_id", client_id)
            if client_secret:
                cfg.set(f"mcp.{catalog_id}_client_secret", client_secret)
            cfg.save()
        else:
            raise ValueError(
                f"No OAuth registration endpoint for {entry.name}. "
                "Use API key Connect if available, or complete OAuth from Cursor first."
            )

        scope = " ".join(str(s) for s in (meta.get("scopes") or [])[:6])
        params = {
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "state": state,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "scope": scope,
            "resource": meta.get("resource") or entry.url,
        }
        authorize_url = (
            str(meta["authorization_endpoint"])
            + "?"
            + urllib.parse.urlencode(params)
        )
        with _oauth_lock:
            _oauth_states[state] = {
                "catalog_id": catalog_id,
                "verifier": verifier,
                "redirect_uri": redirect_uri,
                "client_id": client_id,
                "client_secret": client_secret,
                "token_endpoint": meta["token_endpoint"],
                "resource": meta.get("resource") or entry.url,
                "created_at": time.time(),
            }
        return {
            "authorizeUrl": authorize_url,
            "state": state,
            "redirectUri": redirect_uri,
            "catalogId": catalog_id,
        }

    def complete_oauth(self, *, code: str, state: str) -> dict[str, Any]:
        with _oauth_lock:
            pending = _oauth_states.pop(state, None)
        if not pending:
            raise ValueError("Unknown or expired OAuth state")
        catalog_id = str(pending["catalog_id"])
        entry = get_catalog_entry(catalog_id)
        if entry is None:
            raise KeyError(catalog_id)

        form = {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": pending["redirect_uri"],
            "client_id": pending["client_id"],
            "code_verifier": pending["verifier"],
            "resource": pending["resource"],
        }
        headers: dict[str, str] = {}
        if pending.get("client_secret"):
            import base64

            basic = base64.b64encode(
                f"{pending['client_id']}:{pending['client_secret']}".encode()
            ).decode()
            headers["Authorization"] = f"Basic {basic}"
            form["client_secret"] = pending["client_secret"]

        status, data = _http_json(
            str(pending["token_endpoint"]),
            method="POST",
            form=form,
            headers=headers,
        )
        if status >= 400 or not isinstance(data, dict) or not data.get("access_token"):
            raise ValueError(f"Token exchange failed: {data}")

        cfg = Config.load()
        cfg.set(f"mcp.{catalog_id}_access_token", str(data["access_token"]))
        if data.get("refresh_token"):
            cfg.set(f"mcp.{catalog_id}_refresh_token", str(data["refresh_token"]))
        expires_in = data.get("expires_in")
        if expires_in:
            cfg.set(
                f"mcp.{catalog_id}_token_expires_at",
                str(int(time.time()) + int(expires_in)),
            )
        cfg.save()

        result = probe_mcp_server(
            url=entry.url,
            headers={"Authorization": f"Bearer {data['access_token']}"},
        )
        server = self.ensure_catalog_server(catalog_id, enabled=result["ok"])
        if result["ok"] and not server.enabled:
            server = self.store.update_mcp_server(server.id, enabled=True) or server
        elif not result["ok"] and server.enabled:
            self.store.update_mcp_server(server.id, enabled=False)
        if result["ok"]:
            save_tool_count(catalog_id, int(result.get("toolCount") or 0))
        else:
            clear_tool_count(catalog_id)
            save_status_message(
                catalog_id, str(result.get("message") or "Connection failed")
            )

        return {
            "ok": result["ok"],
            "catalogId": catalog_id,
            "serverId": server.id,
            "enabled": bool(server.enabled),
            **result,
        }

    def resolve_runtime_servers(self) -> list[dict[str, Any]]:
        """Enabled MCP servers with auth headers injected for the agent runtime."""
        cfg = Config.load()
        out: list[dict[str, Any]] = []
        for server in self.store.list_mcp_servers(enabled_only=True):
            payload = server.model_dump(mode="json")
            # Never leak header secrets into the agent context dump.
            payload.pop("header_names", None)
            payload.pop("headers_configured", None)
            catalog_id = getattr(server, "catalog_id", None)
            if catalog_id:
                entry = get_catalog_entry(catalog_id)
                if entry:
                    headers = resolve_auth_headers(entry, cfg)
                    if headers:
                        payload["headers"] = headers
            else:
                headers = resolve_custom_server_headers(server, config=cfg)
                if headers:
                    payload["headers"] = headers
            out.append(payload)
        return out
