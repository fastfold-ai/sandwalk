"""Helpers for talking to the Fastfold Agents API (used by `sandwalk fork`)."""

import json
import os
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path


def _normalize_share_id(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        raise ValueError("share_id is required")
    if "/agents/share/" in raw:
        suffix = raw.split("/agents/share/", 1)[1]
        raw = suffix.split("?", 1)[0].split("#", 1)[0].strip()
    return raw


def _parse_unix_timestamp(value: object) -> float:
    text = str(value or "").strip()
    if not text:
        return time.time()
    if text.endswith("Z"):
        text = f"{text[:-1]}+00:00"
    try:
        return datetime.fromisoformat(text).timestamp()
    except Exception:
        return time.time()


def _resolve_agents_api_base_url(cli_value: str | None = None) -> str:
    candidate = str(cli_value or os.environ.get("FASTFOLD_AGENTS_API_URL") or "").strip()
    if candidate:
        return candidate.rstrip("/")
    return "https://agents-api.fastfold.ai/v1"


def _agents_api_request_json(
    base_url: str,
    path: str,
    *,
    headers: dict[str, str],
    method: str = "GET",
    timeout: float = 20.0,
    body: dict | None = None,
) -> dict:
    url = f"{base_url.rstrip('/')}{path}"
    data: bytes | None = None
    normalized_method = str(method or "GET").upper()
    request_headers = dict(headers or {})
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        request_headers.setdefault("Content-Type", "application/json")
    req = urllib.request.Request(url=url, headers=request_headers, method=normalized_method, data=data)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Agents API {exc.code} for {path}: {detail or exc.reason}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Could not reach Agents API at {url}: {exc}") from exc

    try:
        payload = json.loads(body) if body else {}
    except Exception as exc:
        raise RuntimeError(f"Agents API returned invalid JSON for {path}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError(f"Agents API returned unexpected response for {path}")
    return payload


def _agents_api_get_json(base_url: str, path: str, *, headers: dict[str, str], timeout: float = 20.0) -> dict:
    return _agents_api_request_json(base_url, path, headers=headers, method="GET", timeout=timeout)


def _safe_workspace_relative_path(raw_path: str) -> Path | None:
    normalized = str(raw_path or "").strip().replace("\\", "/").lstrip("/")
    if not normalized:
        return None
    parts = [segment for segment in normalized.split("/") if segment and segment != "."]
    if any(segment == ".." for segment in parts):
        return None
    if not parts:
        return None
    return Path(*parts)


def _download_binary(url: str, *, timeout: float = 30.0) -> bytes:
    req = urllib.request.Request(url=url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read()
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Failed to download shared file from {url}: {exc}") from exc
