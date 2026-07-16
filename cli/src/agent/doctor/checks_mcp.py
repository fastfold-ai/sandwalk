"""Enabled catalog MCP server connectivity probes."""

from __future__ import annotations

from agent.config import Config
from agent.doctor.models import DoctorCheck


def _check_mcp_servers(cfg: Config) -> list[DoctorCheck]:
    """Probe enabled catalog MCP servers (Connect → toggle on)."""
    checks: list[DoctorCheck] = []
    try:
        from agent.mcp_catalog import MCP_CATALOG
        from agent_server.mcp_service import (
            credentials_configured,
            probe_mcp_server,
            resolve_auth_headers,
        )
        from agent_server.store import AgentStore
    except Exception as exc:  # noqa: BLE001
        checks.append(
            DoctorCheck(
                name="mcp_catalog",
                status="warn",
                detail=f"MCP catalog unavailable: {exc}",
                category="mcp",
            )
        )
        return checks

    try:
        store = AgentStore()
        enabled = {
            s.catalog_id: s
            for s in store.list_mcp_servers(enabled_only=True)
            if getattr(s, "catalog_id", None)
        }
    except Exception as exc:  # noqa: BLE001
        checks.append(
            DoctorCheck(
                name="mcp_store",
                status="warn",
                detail=f"Could not load MCP servers: {exc}",
                category="mcp",
                fix="Restart `sandwalk serve`",
            )
        )
        return checks

    for entry in MCP_CATALOG:
        check_name = f"mcp_{entry.id}"
        server = enabled.get(entry.id)
        if server is None:
            # Suggested default off — skip unless credentials exist (stale/misconfig)
            if credentials_configured(entry, cfg):
                checks.append(
                    DoctorCheck(
                        name=check_name,
                        status="warn",
                        detail=f"{entry.name} credentials saved but MCP is disabled",
                        category="mcp",
                        fix="Enable on Dashboard → MCP, or Connect again",
                    )
                )
            continue

        headers = resolve_auth_headers(entry, cfg)
        if not headers:
            checks.append(
                DoctorCheck(
                    name=check_name,
                    status="error",
                    detail=f"{entry.name} is enabled but not authenticated",
                    category="mcp",
                    fix="Dashboard → MCP → Connect (OAuth or API key)",
                )
            )
            continue

        result = probe_mcp_server(url=entry.url, headers=headers, timeout=25.0)
        # Neurosnap accepts Bearer or X-API-KEY — retry alternate if primary fails.
        if not result["ok"] and entry.id == "neurosnap":
            from agent_server.mcp_service import _cfg_secret

            api_key = _cfg_secret(cfg, entry.api_key_config_key, entry.api_key_env_var)
            if api_key:
                for alt in (
                    {"X-API-KEY": api_key},
                    {"Authorization": f"Bearer {api_key}"},
                ):
                    if alt == headers:
                        continue
                    alt_result = probe_mcp_server(
                        url=entry.url, headers=alt, timeout=25.0
                    )
                    if alt_result.get("ok"):
                        result = alt_result
                        break

        if result["ok"]:
            try:
                from agent_server.mcp_service import save_tool_count

                save_tool_count(entry.id, int(result.get("toolCount") or 0))
            except Exception:  # noqa: BLE001
                pass
            checks.append(
                DoctorCheck(
                    name=check_name,
                    status="ok",
                    detail=f"{entry.name}: {result['toolCount']} tools",
                    category="mcp",
                )
            )
        else:
            try:
                from agent_server.mcp_service import clear_tool_count, save_status_message

                clear_tool_count(entry.id)
                save_status_message(
                    entry.id, str(result.get("message") or "Connection failed")
                )
            except Exception:  # noqa: BLE001
                pass
            checks.append(
                DoctorCheck(
                    name=check_name,
                    status="error",
                    detail=f"{entry.name}: {result['message']}",
                    category="mcp",
                    fix="Reconnect on Dashboard → MCP or check API key under Integrations",
                )
            )

    # Also note custom enabled remote MCP servers (no catalog_id)
    try:
        customs = [
            s
            for s in store.list_mcp_servers(enabled_only=True)
            if not getattr(s, "catalog_id", None) and s.url
        ]
        for server in customs[:5]:
            result = probe_mcp_server(url=server.url, headers=None, timeout=15.0)
            status = "ok" if result["ok"] else "warn"
            checks.append(
                DoctorCheck(
                    name=f"mcp_custom_{server.id[:8]}",
                    status=status,
                    detail=f"{server.name}: {result['message']}",
                    category="mcp",
                )
            )
    except Exception:  # noqa: BLE001
        pass

    return checks
