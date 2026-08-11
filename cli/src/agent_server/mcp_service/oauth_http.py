"""Low-level HTTP/PKCE primitives used by OAuth discovery and token exchange."""

from __future__ import annotations

import hashlib
import json
import re
import secrets
import urllib.error
import urllib.parse
import urllib.request
from base64 import urlsafe_b64encode
from typing import Any

from agent_server.mcp_service.custom_headers import ensure_mcp_http_headers


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
    # Cloudflare (and many MCP hosts) ban Python-urllib's default UA — without
    # a real client string, OAuth discovery returns 403 and looks like "no OAuth".
    req_headers = {
        "Accept": "application/json",
        **ensure_mcp_http_headers(headers),
    }
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
    except urllib.error.URLError as exc:
        return 0, {"error": str(exc.reason if hasattr(exc, "reason") else exc)}


def _resource_metadata_url_from_www_authenticate(header: str | None) -> str | None:
    """Parse RFC 9728 resource_metadata from a WWW-Authenticate challenge."""
    if not header:
        return None
    match = re.search(
        r'resource_metadata=(?:"([^"]+)"|([^\s,]+))',
        header,
        flags=re.IGNORECASE,
    )
    if not match:
        return None
    return (match.group(1) or match.group(2) or "").strip() or None


def _probe_resource_metadata_url(mcp_url: str) -> str | None:
    """Unauthenticated MCP call → WWW-Authenticate resource_metadata (MCP spec)."""
    parsed = urllib.parse.urlparse(mcp_url)
    if parsed.scheme not in ("http", "https"):
        return None
    body = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-03-26",
                "capabilities": {},
                "clientInfo": {"name": "sandwalk", "version": "0.1.0"},
            },
        }
    ).encode()
    req = urllib.request.Request(
        mcp_url,
        data=body,
        method="POST",
        headers=ensure_mcp_http_headers(
            {
                "Accept": "application/json, text/event-stream",
                "Content-Type": "application/json",
            }
        ),
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            _ = resp.read()
            return None
    except urllib.error.HTTPError as exc:
        return _resource_metadata_url_from_www_authenticate(
            exc.headers.get("WWW-Authenticate") if exc.headers else None
        )
    except Exception:
        return None
