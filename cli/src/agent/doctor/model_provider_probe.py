"""Probe cloud model-provider /models endpoints and assemble the doctor check."""

from __future__ import annotations

from agent.config import Config
from agent.doctor.model_provider_targets import (
    ProviderTarget,
    gather_cloud_provider_targets,
    gather_local_profile_checks,
)
from agent.doctor.models import DoctorCheck


def _probe_one_target(httpx, label: str, url: str, headers: dict[str, str]) -> DoctorCheck:
    try:
        resp = httpx.get(
            url,
            headers={
                "Accept": "application/json",
                "User-Agent": (
                    "Mozilla/5.0 (compatible; FastFoldAgent/1.0; "
                    "+https://github.com/fastfold-ai/fastfold-agent-cli)"
                ),
                **headers,
            },
            timeout=6,
            follow_redirects=True,
        )
    except Exception as exc:
        return DoctorCheck(
            name=f"Model endpoint · {label}",
            status="warn",
            detail=f"Endpoint unreachable ({exc})",
            category="llm",
        )

    code = resp.status_code
    try:
        body_text = (resp.text or "").strip()
    except Exception:
        body_text = ""
    body_lower = body_text.lower()
    # xAI (and some OpenAI-compatible APIs) return HTTP 400 for bad keys
    # instead of 401/403. Keep those as warnings (not hard failures).
    auth_hint_400 = code == 400 and any(
        marker in body_lower
        for marker in (
            "incorrect api key",
            "invalid api key",
            "invalid_api_key",
            "unauthorized",
            "authentication",
            "api key provided",
        )
    )
    if code == 200:
        count = 0
        try:
            payload = resp.json()
            data = (
                payload.get("data")
                if isinstance(payload, dict)
                else None
            ) or (
                payload.get("models") if isinstance(payload, dict) else None
            )
            count = len(data) if isinstance(data, list) else 0
        except Exception:
            count = 0
        detail = "Reachable, key valid" + (
            f" ({count} models)" if count else ""
        )
        return DoctorCheck(
            name=f"Model endpoint · {label}",
            status="ok",
            detail=detail,
            category="llm",
        )
    if code in (401, 403):
        return DoctorCheck(
            name=f"Model endpoint · {label}",
            status="error",
            detail=f"Authentication failed (HTTP {code}) — check the API key",
            category="llm",
            fix="Update the key in Dashboard → Integrations / Models",
        )
    if auth_hint_400:
        return DoctorCheck(
            name=f"Model endpoint · {label}",
            status="warn",
            detail="HTTP 400: Incorrect API key — update the key to restore this provider",
            category="llm",
            fix="Update the key in Dashboard → Integrations / Models",
        )
    detail = f"Unexpected response (HTTP {code})"
    # Prefer a short provider error message when available.
    try:
        payload = resp.json()
        if isinstance(payload, dict):
            msg = str(
                payload.get("error")
                or payload.get("message")
                or ""
            ).strip()
            if isinstance(payload.get("error"), dict):
                msg = str(
                    payload["error"].get("message")
                    or payload["error"].get("error")
                    or msg
                ).strip()
            if msg:
                detail = f"HTTP {code}: {msg[:160]}"
    except Exception:
        pass
    return DoctorCheck(
        name=f"Model endpoint · {label}",
        status="warn",
        detail=detail,
        category="llm",
    )


def _probe_targets(targets: list[ProviderTarget]) -> list[DoctorCheck]:
    import httpx

    return [_probe_one_target(httpx, label, url, headers) for _prov, label, url, headers, _local in targets]


def _check_model_providers(cfg: Config) -> list[DoctorCheck]:
    """Health-check configured model provider endpoints without spending tokens.

    Uses each provider's model-list endpoint (``GET /models`` for OpenAI-style
    providers, ``GET /v1/models`` for Anthropic). Listing models validates both
    reachability and the API key, and never runs a completion — so it costs no
    tokens.
    """
    try:
        import httpx  # noqa: F401
    except ImportError:
        return [
            DoctorCheck(
                name="model_providers",
                status="warn",
                detail="httpx not installed — skipping model endpoint checks",
                category="llm",
            )
        ]

    checks = gather_local_profile_checks(cfg)
    targets = gather_cloud_provider_targets(cfg)

    if not targets and not checks:
        return [
            DoctorCheck(
                name="Model endpoints",
                status="warn",
                detail="No model provider API keys or local endpoints configured",
                category="llm",
            )
        ]

    checks.extend(_probe_targets(targets))
    return checks
