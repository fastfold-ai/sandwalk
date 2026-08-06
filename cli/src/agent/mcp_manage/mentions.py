"""Resolve ``mcp:`` composer chips into prompt steering (like skill mentions).

Chip insert alone is soft text — weaker models often ignore it and search the
web/HF for the product name. This module extracts mentions and builds a short
runtime reminder that lists loaded tool schemas for the pointed-at server.
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import unquote

# Web composer chip: ⟦mcp:id:name⟧ (URI-encoded segments).
_MCP_TOKEN_RE = re.compile(r"⟦mcp:([^⟧]+)⟧")
# CLI ``mcp: raymol`` (space) and web ``mcp:Linear`` / ``mcp:RayMol``.
_MCP_PLAIN_RE = re.compile(
    r"(?:^|[\s(\[\"'])(mcp:\s*[^\s]+)(?=[\s.,;:!?)\]\"'`]|$)",
    re.IGNORECASE,
)

_MAX_MENTIONED_MCPS = 4
_MAX_TOOLS_LISTED = 24


def _normalize_key(value: str) -> str:
    text = unquote(str(value or "")).strip().lower()
    text = text.replace("_", "-").replace(" ", "-")
    return text


def _mention_from_plain(raw: str) -> str:
    body = str(raw or "").strip()
    if body.lower().startswith("mcp:"):
        body = body[4:]
    return unquote(body.strip())


def _mention_from_token(raw: str) -> str:
    """Prefer catalog id from ``id:name`` chip payload; fall back to name."""
    payload = str(raw or "").strip()
    if not payload:
        return ""
    if ":" in payload:
        left, right = payload.split(":", 1)
        left_id = unquote(left).strip()
        right_name = unquote(right).strip()
        return left_id or right_name
    return unquote(payload).strip()


def extract_mcp_mentions(text: str) -> list[str]:
    """Return unique MCP mention keys (catalog id or display name) in order."""
    raw = str(text or "")
    hits: list[tuple[int, str]] = []

    for match in _MCP_TOKEN_RE.finditer(raw):
        key = _mention_from_token(match.group(1) or "")
        if key:
            hits.append((match.start(), key))

    for match in _MCP_PLAIN_RE.finditer(raw):
        token = match.group(1) or ""
        key = _mention_from_plain(token)
        if not key:
            continue
        start = match.start() + match.group(0).index(token)
        hits.append((start, key))

    hits.sort(key=lambda item: item[0])
    out: list[str] = []
    seen: set[str] = set()
    for _, key in hits:
        norm = _normalize_key(key)
        if not norm or norm in seen:
            continue
        seen.add(norm)
        out.append(key)
    return out


def _server_keys(server: dict[str, Any]) -> list[str]:
    keys: list[str] = []
    for field in ("catalog_id", "id", "name"):
        value = str(server.get(field) or "").strip()
        if value:
            keys.append(value)
    return keys


def _match_server(
    mention: str,
    servers: list[dict[str, Any]],
) -> dict[str, Any] | None:
    want = _normalize_key(mention)
    if not want:
        return None
    for server in servers:
        for key in _server_keys(server):
            if _normalize_key(key) == want:
                return server
    return None


def _match_catalog(mention: str):
    want = _normalize_key(mention)
    if not want:
        return None
    try:
        from agent.mcp_catalog import MCP_CATALOG
    except Exception:  # noqa: BLE001
        return None
    for entry in MCP_CATALOG:
        if _normalize_key(entry.id) == want or _normalize_key(entry.name) == want:
            return entry
    return None


def _tool_names_for(
    server: dict[str, Any],
    tools_by_server: dict[str, list[str]] | None,
) -> list[str]:
    if not tools_by_server:
        return []
    for key in _server_keys(server):
        names = tools_by_server.get(_normalize_key(key))
        if names:
            return list(names)
        names = tools_by_server.get(key)
        if names:
            return list(names)
    return []


def build_mcp_mention_context(
    text: str,
    *,
    mcp_servers: list[dict[str, Any]] | None = None,
    mcp_tools_by_server: dict[str, list[str]] | None = None,
    max_mcps: int = _MAX_MENTIONED_MCPS,
) -> str:
    """Build a prefer-this-MCP reminder for ``mcp:`` chips in the user message."""
    mentions = extract_mcp_mentions(text)
    if not mentions:
        return ""

    enabled = [dict(s) for s in (mcp_servers or []) if isinstance(s, dict)]
    # Also consider disabled store entries so we can warn clearly.
    store_servers: list[dict[str, Any]] = []
    try:
        from agent_server.store import AgentStore

        store_servers = [
            dict(s) for s in AgentStore().list_mcp_servers() if isinstance(s, dict)
        ]
    except Exception:  # noqa: BLE001
        store_servers = []

    active: list[tuple[str, dict[str, Any], list[str]]] = []
    disabled: list[str] = []
    unknown: list[str] = []

    for mention in mentions:
        if len(active) >= max(1, int(max_mcps)):
            break
        matched = _match_server(mention, enabled)
        if matched is not None and matched.get("enabled", True):
            tools = _tool_names_for(matched, mcp_tools_by_server)
            active.append((mention, matched, tools))
            continue
        store_hit = _match_server(mention, store_servers)
        if store_hit is not None and not store_hit.get("enabled", True):
            label = str(
                store_hit.get("name")
                or store_hit.get("catalog_id")
                or store_hit.get("id")
                or mention
            ).strip()
            disabled.append(label)
            continue
        catalog = _match_catalog(mention)
        if catalog is not None:
            disabled.append(catalog.name)
            continue
        if store_hit is not None:
            # Present in store but filtered out of this turn (specialist, etc.).
            label = str(
                store_hit.get("name")
                or store_hit.get("catalog_id")
                or mention
            ).strip()
            disabled.append(label)
            continue
        unknown.append(mention)

    if not active and not disabled and not unknown:
        return ""

    lines: list[str] = [
        "User mentioned MCP server(s) via an `mcp:` chip. Treat that as a hard "
        "preference for this turn: use that server's tool schemas first.",
        "Do not search the web, Hugging Face, or the filesystem for the product "
        "name unless the user explicitly asked for that — call the MCP tools.",
    ]

    if active:
        lines.append("Preferred MCP server(s) (tools already bound for this turn):")
        for mentioned_as, server, tools in active:
            label = str(
                server.get("name")
                or server.get("catalog_id")
                or server.get("id")
                or mentioned_as
            ).strip()
            catalog_id = str(server.get("catalog_id") or "").strip()
            identity = f"{label}"
            if catalog_id and _normalize_key(catalog_id) != _normalize_key(label):
                identity = f"{label} (`{catalog_id}`)"
            lines.append(f"- {identity} (mentioned as mcp:{mentioned_as})")
            desc = str(server.get("description") or "").strip()
            if desc:
                lines.append(f"  {desc}")
            if tools:
                shown = tools[:_MAX_TOOLS_LISTED]
                more = len(tools) - len(shown)
                listing = ", ".join(f"`{name}`" for name in shown)
                if more > 0:
                    listing = f"{listing}, …(+{more} more)"
                lines.append(f"  Call these tools by name: {listing}")
            else:
                lines.append(
                    "  Tools from this server are in your tool list — prefer "
                    "them over domain/search tools for this request."
                )

    if disabled:
        names = ", ".join(disabled)
        lines.append(
            f"Mentioned but not enabled/available this turn: {names}. "
            "Tell the user to enable the server in MCP settings (and complete "
            "any local Allow/setup step), then retry — do not improvise via web search."
        )

    if unknown:
        names = ", ".join(unknown)
        lines.append(
            f"Mentioned MCP not found in config/catalog: {names}. "
            "Ask the user to add/enable it under MCP settings."
        )

    return "\n".join(lines).strip()
