"""Quiet OpenAI-compatible model discovery for agent-server / CLI internals."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any
from urllib.parse import urlparse

# Cloudflare (and similar edges) block bare Python-urllib clients with Error 1010.
# A browser-like User-Agent is required for OpenCode Zen/Go /v1/models.
_DEFAULT_HEADERS = {
    "Accept": "application/json",
    "User-Agent": (
        "Mozilla/5.0 (compatible; FastFoldAgent/1.0; "
        "+https://github.com/fastfold-ai/fastfold-agent-cli)"
    ),
}


def ollama_tags_url_from_base(base_url: str) -> str:
    parsed = urlparse(str(base_url or "").strip())
    path = (parsed.path or "").rstrip("/")
    if path.endswith("/v1"):
        path = path[:-3]
    tags_path = f"{path}/api/tags" if path else "/api/tags"
    return parsed._replace(path=tags_path, query="", fragment="").geturl()


def openai_models_url_from_base(base_url: str) -> str:
    parsed = urlparse(str(base_url or "").strip())
    path = (parsed.path or "").rstrip("/")
    if not path.endswith("/v1"):
        path = f"{path}/v1" if path else "/v1"
    models_path = f"{path}/models"
    return parsed._replace(path=models_path, query="", fragment="").geturl()


def _request_json(url: str, api_key: str | None, *, timeout: float = 10.0) -> tuple[Any | None, str | None]:
    headers = dict(_DEFAULT_HEADERS)
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    req = urllib.request.Request(url=url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            text = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        status = int(getattr(exc, "code", 0) or 0)
        reason = str(getattr(exc, "reason", "") or getattr(exc, "msg", "")).strip()
        return None, f"HTTP {status or 'error'}{f': {reason}' if reason else ''} ({url})"
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return None, f"{exc} ({url})"
    except Exception as exc:  # pragma: no cover - defensive
        return None, f"{exc} ({url})"
    try:
        return (json.loads(text) if text else {}), None
    except Exception:
        return None, f"Invalid JSON from {url}"


def fetch_openai_models(base_url: str, api_key: str | None = None) -> tuple[list[str], str | None]:
    url = openai_models_url_from_base(base_url)
    payload, err = _request_json(url, api_key)
    if err:
        return [], err
    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, list):
        return [], f"Unexpected /v1/models payload ({url})"
    names = sorted(
        {str(item.get("id") or "").strip() for item in data if isinstance(item, dict)} - {""}
    )
    return names, None


def fetch_ollama_tags(base_url: str, api_key: str | None = None) -> tuple[list[str], str | None]:
    url = ollama_tags_url_from_base(base_url)
    payload, err = _request_json(url, api_key)
    if err:
        return [], err
    models = payload.get("models") if isinstance(payload, dict) else None
    if not isinstance(models, list):
        return [], f"Unexpected /api/tags payload ({url})"
    names = sorted(
        {str(item.get("name") or "").strip() for item in models if isinstance(item, dict)} - {""}
    )
    return names, None


def discover_compatible_models(
    base_url: str,
    backend: str,
    api_key: str | None = None,
) -> tuple[list[str], str, str | None]:
    """
    Discover models for a compatible backend.

    Returns (model_ids, source_path, error_or_none).
    """
    backend_type = str(backend or "").strip().lower() or "other"
    errors: list[str] = []

    if backend_type in {"unsloth", "omlx", "ds4", "llama_cpp", "lm_studio"}:
        models, err = fetch_openai_models(base_url, api_key=api_key)
        if err:
            errors.append(err)
        return models, "/v1/models", ("; ".join(errors) if errors and not models else None)

    if backend_type == "ollama":
        models, err = fetch_ollama_tags(base_url, api_key=api_key)
        source = "/api/tags"
        if err:
            errors.append(err)
        if not models:
            models, err2 = fetch_openai_models(base_url, api_key=api_key)
            source = "/v1/models"
            if err2:
                errors.append(err2)
        return models, source, ("; ".join(errors) if errors and not models else None)

    models, err = fetch_openai_models(base_url, api_key=api_key)
    source = "/v1/models"
    if err:
        errors.append(err)
    if not models:
        models, err2 = fetch_ollama_tags(base_url, api_key=api_key)
        source = "/api/tags"
        if err2:
            errors.append(err2)
    return models, source, ("; ".join(errors) if errors and not models else None)


def probe_compatible_profile(
    *,
    base_url: str,
    backend: str,
    api_key: str | None,
) -> dict[str, Any]:
    models, source, error = discover_compatible_models(base_url, backend, api_key=api_key)
    if models:
        health = "healthy"
    elif error:
        health = "error"
    else:
        health = "no_models"
    return {
        "health": health,
        "models": models,
        "models_source": source,
        "models_path": source,
        "error": error,
    }
