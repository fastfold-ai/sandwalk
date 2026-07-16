"""MCP initialize + tools/list smoke test over HTTP."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any

from agent_server.mcp_service.custom_headers import ensure_mcp_http_headers


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
        req_headers = ensure_mcp_http_headers(
            {
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
                **(headers or {}),
            }
        )
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

    empty = {
        "ok": False,
        "toolCount": 0,
        "message": "",
        "tools": [],
        "toolDetails": [],
    }

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
            **empty,
            "message": f"initialize failed HTTP {status}: {raw[:300]}",
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
            **empty,
            "message": f"tools/list failed HTTP {status2}: {raw2[:300]}",
        }
    msg = msgs[0]
    if "error" in msg:
        err = msg["error"]
        detail = err.get("message") if isinstance(err, dict) else str(err)
        return {**empty, "message": str(detail)}
    tools = (msg.get("result") or {}).get("tools") or []
    details: list[dict[str, Any]] = []
    names: list[str] = []
    for tool in tools:
        if not isinstance(tool, dict):
            continue
        name = str(tool.get("name") or "").strip()
        if not name:
            continue
        names.append(name)
        schema = tool.get("inputSchema")
        if schema is None:
            schema = tool.get("input_schema")
        title = str(tool.get("title") or "").strip() or None
        if not title:
            annotations = tool.get("annotations")
            if isinstance(annotations, dict):
                title = str(annotations.get("title") or "").strip() or None
        details.append(
            {
                "name": name,
                "title": title,
                "description": str(tool.get("description") or "").strip() or None,
                "inputSchema": schema if isinstance(schema, dict) else None,
            }
        )
    init_msgs = parse_sse_or_json(raw)
    server_info = None
    if init_msgs:
        server_info = (init_msgs[0].get("result") or {}).get("serverInfo")
    return {
        "ok": True,
        "toolCount": len(details),
        "message": f"Connected — {len(details)} tools available",
        "tools": names,
        "toolDetails": details,
        "serverInfo": server_info,
    }
