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


def ollama_show_url_from_base(base_url: str) -> str:
    parsed = urlparse(str(base_url or "").strip())
    path = (parsed.path or "").rstrip("/")
    if path.endswith("/v1"):
        path = path[:-3]
    show_path = f"{path}/api/show" if path else "/api/show"
    return parsed._replace(path=show_path, query="", fragment="").geturl()


def openai_models_url_from_base(base_url: str) -> str:
    parsed = urlparse(str(base_url or "").strip())
    path = (parsed.path or "").rstrip("/")
    if not path.endswith("/v1"):
        path = f"{path}/v1" if path else "/v1"
    models_path = f"{path}/models"
    return parsed._replace(path=models_path, query="", fragment="").geturl()


def _request_json(
    url: str,
    api_key: str | None,
    *,
    timeout: float = 10.0,
    method: str = "GET",
    body: dict[str, Any] | None = None,
) -> tuple[Any | None, str | None]:
    headers = dict(_DEFAULT_HEADERS)
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    data = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url=url, headers=headers, method=method, data=data)
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


def _context_window_from_model_item(item: dict[str, Any]) -> int | None:
    for key in (
        "max_model_len",
        "context_length",
        "context_window",
        "max_context_length",
        "max_position_embeddings",
    ):
        raw = item.get(key)
        if raw is None:
            continue
        try:
            value = int(raw)
        except (TypeError, ValueError):
            continue
        if value > 0:
            return value
    return None


def _context_window_from_ollama_model_info(model_info: dict[str, Any]) -> int | None:
    best: int | None = None
    for key, raw in model_info.items():
        if not (key == "context_length" or key.endswith(".context_length")):
            continue
        try:
            value = int(raw)
        except (TypeError, ValueError):
            continue
        if value > 0 and (best is None or value > best):
            best = value
    if best is not None:
        return best
    return _context_window_from_model_item(model_info)


def fetch_ollama_show_context(
    base_url: str,
    model_name: str,
    api_key: str | None = None,
) -> int | None:
    """Read native context length from Ollama /api/show when /api/tags omits it."""
    name = str(model_name or "").strip()
    if not name:
        return None
    url = ollama_show_url_from_base(base_url)
    payload, err = _request_json(
        url,
        api_key,
        method="POST",
        body={"model": name},
    )
    if err or not isinstance(payload, dict):
        return None
    model_info = payload.get("model_info")
    if not isinstance(model_info, dict):
        return None
    return _context_window_from_ollama_model_info(model_info)


def fetch_openai_models(
    base_url: str, api_key: str | None = None
) -> tuple[list[str], str | None]:
    names, _windows, err = fetch_openai_models_with_context(base_url, api_key)
    return names, err


def fetch_openai_models_with_context(
    base_url: str, api_key: str | None = None
) -> tuple[list[str], dict[str, int], str | None]:
    url = openai_models_url_from_base(base_url)
    payload, err = _request_json(url, api_key)
    if err:
        return [], {}, err
    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, list):
        return [], {}, f"Unexpected /v1/models payload ({url})"
    names: list[str] = []
    windows: dict[str, int] = {}
    for item in data:
        if not isinstance(item, dict):
            continue
        model_id = str(item.get("id") or "").strip()
        if not model_id:
            continue
        names.append(model_id)
        context_window = _context_window_from_model_item(item)
        if context_window is not None:
            windows[model_id] = context_window
    names = sorted(set(names))
    return names, windows, None


def fetch_ollama_tags(base_url: str, api_key: str | None = None) -> tuple[list[str], str | None]:
    names, _windows, err = fetch_ollama_tags_with_context(base_url, api_key)
    return names, err


def fetch_ollama_tags_with_context(
    base_url: str, api_key: str | None = None
) -> tuple[list[str], dict[str, int], str | None]:
    url = ollama_tags_url_from_base(base_url)
    payload, err = _request_json(url, api_key)
    if err:
        return [], {}, err
    models = payload.get("models") if isinstance(payload, dict) else None
    if not isinstance(models, list):
        return [], {}, f"Unexpected /api/tags payload ({url})"
    names: list[str] = []
    windows: dict[str, int] = {}
    for item in models:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        if not name:
            continue
        names.append(name)
        # Newer Ollama includes the model's context length in tag details.
        details = item.get("details")
        source = details if isinstance(details, dict) else item
        context_window = _context_window_from_model_item(source)
        if context_window is not None:
            windows[name] = context_window
    names = sorted(set(names))
    # Custom/MLX imports often omit details.context_length in /api/tags; /api/show has it.
    for name in names:
        if name in windows:
            continue
        context_window = fetch_ollama_show_context(base_url, name, api_key=api_key)
        if context_window is not None:
            windows[name] = context_window
    return names, windows, None


def discover_compatible_models(
    base_url: str,
    backend: str,
    api_key: str | None = None,
) -> tuple[list[str], str, str | None, dict[str, int]]:
    """
    Discover models for a compatible backend.

    Returns (model_ids, source_path, error_or_none, context_windows).
    """
    backend_type = str(backend or "").strip().lower() or "other"
    errors: list[str] = []
    windows: dict[str, int] = {}

    if backend_type in {"unsloth", "omlx", "ds4", "llama_cpp", "lm_studio"}:
        models, windows, err = fetch_openai_models_with_context(
            base_url, api_key=api_key
        )
        if err:
            errors.append(err)
        return (
            models,
            "/v1/models",
            ("; ".join(errors) if errors and not models else None),
            windows,
        )

    if backend_type == "ollama":
        models, windows, err = fetch_ollama_tags_with_context(base_url, api_key=api_key)
        source = "/api/tags"
        if err:
            errors.append(err)
        if not models:
            models, windows, err2 = fetch_openai_models_with_context(
                base_url, api_key=api_key
            )
            source = "/v1/models"
            if err2:
                errors.append(err2)
        return (
            models,
            source,
            ("; ".join(errors) if errors and not models else None),
            windows,
        )

    models, windows, err = fetch_openai_models_with_context(base_url, api_key=api_key)
    source = "/v1/models"
    if err:
        errors.append(err)
    if not models:
        models, windows, err2 = fetch_ollama_tags_with_context(
            base_url, api_key=api_key
        )
        source = "/api/tags"
        if err2:
            errors.append(err2)
    return (
        models,
        source,
        ("; ".join(errors) if errors and not models else None),
        windows,
    )


def probe_compatible_profile(
    *,
    base_url: str,
    backend: str,
    api_key: str | None,
) -> dict[str, Any]:
    models, source, error, context_windows = discover_compatible_models(
        base_url, backend, api_key=api_key
    )
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
        "context_windows": context_windows,
        "error": error,
    }
