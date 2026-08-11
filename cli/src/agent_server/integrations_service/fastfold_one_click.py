"""One-click FastFold Cloud API key grant for Sandwalk desktop."""

from __future__ import annotations

import json
import platform
import sys
import threading
import urllib.error
import urllib.request
from typing import TYPE_CHECKING, Any

from agent_server.account_service.helpers import cloud_base_url
from agent_server.connectors.service import local_oauth_return_url

if TYPE_CHECKING:
    from agent_server.integrations_service import IntegrationsService

_lock = threading.Lock()
# Desktop is single-user: keep the latest claim token until import succeeds.
_pending_claim_token: str | None = None


def _device_label() -> str:
    """Vercel-style device line for the Cloud authorize page.

    Example:
    Julios-MacBook-Pro.local @ sandwalk 0.0.1 python-v3.14.0 darwin (arm64)
    """
    try:
        from _version import __version__ as version
    except Exception:
        version = "unknown"
    host = platform.node() or "unknown-host"
    system = (platform.system() or "unknown").lower()
    if system.startswith("win"):
        system = "win32"
    machine = (platform.machine() or "").lower()
    if machine in {"x86_64", "amd64"}:
        machine = "x64"
    elif machine in {"aarch64"}:
        machine = "arm64"
    py = f"python-v{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    # sandwalk serve / CLI is the runtime that starts the allow flow.
    parts = [f"{host} @ sandwalk {version}", py, system]
    if machine:
        parts.append(f"({machine})")
    return " ".join(parts)


def _network_meta() -> dict[str, str]:
    """Public IP + rough location from the desktop network (not the Cloud API host)."""
    endpoints = (
        "http://ip-api.com/json/?fields=status,query,city,country",
        "https://get.geojs.io/v1/ip/geo.json",
        "https://ipwho.is/",
    )
    for url in endpoints:
        try:
            request = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(request, timeout=3) as response:
                payload = json.loads(response.read() or b"{}")
        except Exception:
            continue
        if not isinstance(payload, dict):
            continue
        if payload.get("status") == "fail" or payload.get("success") is False:
            continue
        if payload.get("error") is True:
            continue
        ip = str(payload.get("query") or payload.get("ip") or "").strip()
        city = str(payload.get("city") or "").strip()
        country = str(payload.get("country") or "").strip()
        location = ", ".join(part for part in (city, country) if part)
        meta: dict[str, str] = {}
        if ip:
            meta["client_ip"] = ip
        if location:
            meta["location"] = location
        if meta:
            return meta
    return {}


def _cloud_json(
    method: str,
    url: str,
    *,
    body: dict[str, Any] | None = None,
    bearer: str | None = None,
) -> tuple[dict[str, Any] | None, str | None]:
    data = json.dumps(body).encode() if body is not None else None
    request = urllib.request.Request(url, data=data, method=method)
    if bearer:
        request.add_header("Authorization", f"Bearer {bearer}")
    if data is not None:
        request.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.loads(response.read() or b"{}")
            return payload if isinstance(payload, dict) else {}, None
    except urllib.error.HTTPError as exc:
        detail = ""
        try:
            detail = exc.read().decode("utf-8", errors="ignore").strip()
        except Exception:
            detail = ""
        if exc.code == 409:
            return None, "not_ready"
        if detail:
            try:
                parsed = json.loads(detail)
                message = str(parsed.get("message") or parsed.get("detail") or "").strip()
                if message:
                    return None, message
            except Exception:
                pass
            return None, detail[:200]
        return None, f"FastFold Cloud returned HTTP {exc.code}."
    except Exception as exc:
        return None, f"Couldn't reach FastFold Cloud ({exc.__class__.__name__})."


def _localize_auth_url(auth_url: str) -> str:
    """When Cloud API is local, open the local Cloud UI consent page."""
    base = cloud_base_url().lower()
    if "127.0.0.1" not in base and "localhost" not in base:
        return auth_url
    localized = auth_url
    for host in (
        "https://cloud.fastfold.ai",
        "http://cloud.fastfold.ai",
        "https://www.fastfold.ai",
    ):
        localized = localized.replace(host, "http://localhost:3000")
    return localized


def start_fastfold_one_click(*, return_to: str | None = None) -> str:
    """Start Cloud grant and return the browser auth URL."""
    global _pending_claim_token
    body = {
        "return_to": return_to or local_oauth_return_url(),
        "device_label": _device_label(),
        **_network_meta(),
    }
    payload, error = _cloud_json(
        "POST",
        f"{cloud_base_url()}/v1/sandwalk/oauth/start",
        body=body,
    )
    if error:
        raise ValueError(error)
    auth_url = _localize_auth_url(str((payload or {}).get("auth_url") or "").strip())
    claim_token = str((payload or {}).get("claim_token") or "").strip()
    if not auth_url or not claim_token:
        raise ValueError("FastFold Cloud did not return a Sandwalk allow URL.")
    with _lock:
        _pending_claim_token = claim_token
    return auth_url


def import_fastfold_one_click(
    integrations: "IntegrationsService",
) -> dict[str, Any]:
    """Claim a minted key (if ready) and persist it as FASTFOLD_API_KEY."""
    global _pending_claim_token
    with _lock:
        claim_token = _pending_claim_token
    if not claim_token:
        raise ValueError("No Sandwalk allow request in progress. Click Add again.")

    payload, error = _cloud_json(
        "POST",
        f"{cloud_base_url()}/v1/sandwalk/oauth/claim",
        body={"claim_token": claim_token},
        bearer=claim_token,
    )
    if error == "not_ready":
        return {"ready": False}
    if error:
        raise ValueError(error)

    api_key = str((payload or {}).get("api_key") or "").strip()
    if not api_key:
        return {"ready": False}

    provider = integrations.update(
        "fastfold-cloud",
        {"FASTFOLD_API_KEY": api_key},
    )
    with _lock:
        if _pending_claim_token == claim_token:
            _pending_claim_token = None
    return {
        "ready": True,
        "provider": provider,
        "team_id": (payload or {}).get("team_id"),
    }


def clear_fastfold_one_click() -> None:
    global _pending_claim_token
    with _lock:
        _pending_claim_token = None
