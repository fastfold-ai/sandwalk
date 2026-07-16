"""Live model-discovery fetches (/v1/models, /api/tags) for compatible endpoints."""

import json
import urllib.error
import urllib.request

from cli.app import console, spinner
from cli.setup.discovery import (
    _ollama_tags_url_from_base,
    _openai_models_url_from_base,
    _report_discovery_exception,
    _report_discovery_http_error,
)
from cli.setup.openai_endpoint import _normalize_compatible_backend_name


def _fetch_openai_models_for_setup(base_url: str, api_key: str | None = None) -> list[str]:
    """Fetch model IDs from OpenAI-compatible /v1/models."""
    url = _openai_models_url_from_base(base_url)
    headers = {"Accept": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    req = urllib.request.Request(url=url, headers=headers, method="GET")
    try:
        with spinner("Discovering models from /v1/models..."):
            with urllib.request.urlopen(req, timeout=4.0) as resp:
                text = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        _report_discovery_http_error("/v1/models", url, exc)
        return []
    except (urllib.error.URLError, TimeoutError) as exc:
        _report_discovery_exception("/v1/models", url, exc)
        return []
    except Exception as exc:
        _report_discovery_exception("/v1/models", url, exc)
        return []
    try:
        payload = json.loads(text) if text else {}
    except Exception:
        return []
    data = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(data, list):
        return []
    names = sorted({str(item.get("id") or "").strip() for item in data if isinstance(item, dict)} - {""})
    if names:
        console.print(f"  [green]Found {len(names)} model(s) from /v1/models.[/green]")
    return names


def _fetch_ollama_tags_for_setup(base_url: str, api_key: str | None = None) -> list[str]:
    """Fetch model names from Ollama /api/tags."""
    url = _ollama_tags_url_from_base(base_url)
    headers = {"Accept": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    req = urllib.request.Request(url=url, headers=headers, method="GET")
    try:
        with spinner("Discovering models from /api/tags..."):
            with urllib.request.urlopen(req, timeout=4.0) as resp:
                text = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        _report_discovery_http_error("/api/tags", url, exc)
        return []
    except (urllib.error.URLError, TimeoutError) as exc:
        _report_discovery_exception("/api/tags", url, exc)
        return []
    except Exception as exc:
        _report_discovery_exception("/api/tags", url, exc)
        return []
    try:
        payload = json.loads(text) if text else {}
    except Exception:
        return []
    models = payload.get("models") if isinstance(payload, dict) else None
    if not isinstance(models, list):
        return []
    names = sorted({str(item.get("name") or "").strip() for item in models if isinstance(item, dict)} - {""})
    if names:
        console.print(f"  [green]Found {len(names)} model(s) from /api/tags.[/green]")
    return names


def _fetch_compatible_models_for_setup(base_url: str, backend: str, api_key: str | None = None) -> list[str]:
    """Discover compatible models based on selected backend."""
    backend_type = _normalize_compatible_backend_name(backend)
    if backend_type in {"unsloth", "omlx", "ds4", "llama_cpp", "lm_studio"}:
        names = _fetch_openai_models_for_setup(base_url, api_key=api_key)
    elif backend_type == "ollama":
        names = _fetch_ollama_tags_for_setup(base_url, api_key=api_key)
        if not names:
            names = _fetch_openai_models_for_setup(base_url, api_key=api_key)
    else:
        names = _fetch_openai_models_for_setup(base_url, api_key=api_key)
        if not names:
            names = _fetch_ollama_tags_for_setup(base_url, api_key=api_key)
    if names:
        return names
    console.print(
        "  [yellow]No models found from discovery endpoint(s).[/yellow] "
        "[dim]You can still enter a model manually.[/dim]"
    )
    return []
