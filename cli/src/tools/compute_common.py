"""Shared provider-data loading and lookup helpers for GPU compute tools."""

import json
from pathlib import Path

from tools.http_client import request_json

_providers_data = None


def _load_providers() -> dict:
    """Load provider data from JSON, caching after first read."""
    global _providers_data
    if _providers_data is None:
        json_path = Path(__file__).resolve().parent.parent / "data" / "compute_providers.json"
        with open(json_path) as f:
            _providers_data = json.load(f)
    return _providers_data


def _provider_info(provider_id: str) -> dict | None:
    """Return provider metadata by ID."""
    data = _load_providers()
    for provider in data.get("providers", []):
        if provider.get("id") == provider_id:
            return provider
    return None


def _provider_api_key_config(provider: str) -> str:
    """Map provider IDs to config keys, with a predictable fallback."""
    key_map = {"lambda": "compute.lambda_api_key", "runpod": "compute.runpod_api_key"}
    return key_map.get(provider, f"compute.{provider}_api_key")


def _resolve_provider(provider: str | None, cfg) -> str:
    """Resolve provider from argument or config default."""
    if provider:
        return provider
    resolved = cfg.get("compute.default_provider", "lambda")
    return resolved or "lambda"


def _request_json(
    method: str,
    url: str,
    *,
    headers: dict,
    payload: dict | None = None,
    timeout: int = 30,
    retries: int = 2,
) -> tuple[dict | None, str | None]:
    """HTTP request with shared retry/backoff semantics."""
    return request_json(
        method,
        url,
        json=payload,
        headers=headers,
        timeout=timeout,
        retries=retries,
    )


def _find_cheapest_gpu(min_vram_gb: int, provider_id: str = None, data: dict = None) -> dict | None:
    """Find the cheapest GPU meeting VRAM requirements, optionally filtered by provider."""
    if data is None:
        data = _load_providers()
    candidates = []
    for provider in data["providers"]:
        if provider_id and provider["id"] != provider_id:
            continue
        for gpu in provider["gpu_types"]:
            if gpu["vram_gb"] >= min_vram_gb:
                candidates.append({
                    "provider_id": provider["id"],
                    "provider_name": provider["name"],
                    "gpu_id": gpu["id"],
                    "gpu_name": gpu["name"],
                    "vram_gb": gpu["vram_gb"],
                    "price_per_hour": gpu["price_per_hour"],
                })
    if not candidates:
        return None
    return min(candidates, key=lambda c: c["price_per_hour"])
