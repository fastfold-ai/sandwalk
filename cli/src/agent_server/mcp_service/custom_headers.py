"""Static custom HTTP header storage for MCP servers (config-backed)."""

from __future__ import annotations

import json

from agent.config import Config

# Cloudflare (Better Stack and others) ban Python-urllib's default UA (Error 1010).
MCP_HTTP_USER_AGENT = (
    "Sandwalk/0.1 (MCP; +https://github.com/fastfold-ai/sandwalk)"
)


def ensure_mcp_http_headers(headers: dict[str, str] | None = None) -> dict[str, str]:
    """Merge caller headers with defaults Cloudflare-friendly MCP clients need."""
    out = {str(k): str(v) for k, v in (headers or {}).items() if str(k).strip()}
    if not any(k.lower() == "user-agent" for k in out):
        out["User-Agent"] = MCP_HTTP_USER_AGENT
    return out


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
