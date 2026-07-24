"""Probe cloud model-provider endpoints and assemble the doctor check."""

from __future__ import annotations

from agent.config import OPENAI_COMPATIBLE_PROVIDERS, Config
from agent.doctor.model_provider_http import (
    ModelsProbeResult,
    probe_llm_api_key,
    supports_llm_key_probe,
)
from agent.doctor.model_provider_targets import gather_local_profile_checks
from agent.doctor.models import DoctorCheck


def _doctor_check_from_probe(label: str, result: ModelsProbeResult) -> DoctorCheck:
    name = f"Model endpoint · {label}"
    if result.ok:
        detail = result.message.replace(
            f"{label} API key works", "Reachable, key valid"
        )
        return DoctorCheck(name=name, status="ok", detail=detail, category="llm")
    if result.status_code in (401, 403) or result.message == "Invalid API key.":
        return DoctorCheck(
            name=name,
            status="error",
            detail="Authentication failed — check the API key",
            category="llm",
            fix="Update the key in Dashboard → Integrations / Models",
        )
    if result.message.startswith("Couldn't reach"):
        return DoctorCheck(
            name=name,
            status="warn",
            detail=f"Endpoint unreachable ({result.message})",
            category="llm",
        )
    return DoctorCheck(
        name=name,
        status="warn",
        detail=result.message,
        category="llm",
        fix="Update the key in Dashboard → Integrations / Models",
    )


def _configured_llm_providers(cfg: Config) -> list[tuple[str, str, str]]:
    """Return ``(provider_key, label, api_key)`` for configured cloud LLMs."""
    import os

    out: list[tuple[str, str, str]] = []

    anthropic = cfg._normalized_secret(
        cfg.get("llm.anthropic_api_key") or cfg.get("llm.api_key")
    ) or cfg._normalized_secret(os.environ.get("ANTHROPIC_API_KEY"))
    if anthropic:
        out.append(("anthropic", "Anthropic", anthropic))

    openai = cfg._normalized_secret(cfg.get("llm.openai_api_key")) or cfg._normalized_secret(
        os.environ.get("OPENAI_API_KEY")
    )
    if openai:
        out.append(("openai", "OpenAI", openai))

    for prov, meta in OPENAI_COMPATIBLE_PROVIDERS.items():
        if not supports_llm_key_probe(prov):
            continue
        key = cfg.llm_api_key(prov)
        if not key:
            continue
        out.append((prov, str(meta.get("label") or prov), key))
    return out


def _check_model_providers(cfg: Config) -> list[DoctorCheck]:
    """Health-check configured model providers with a 1-token auth call each."""
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
    cloud = _configured_llm_providers(cfg)

    if not cloud and not checks:
        return [
            DoctorCheck(
                name="Model endpoints",
                status="warn",
                detail="No model provider API keys or local endpoints configured",
                category="llm",
            )
        ]

    for provider_key, label, api_key in cloud:
        result = probe_llm_api_key(provider_key, api_key, label=label, timeout=30)
        checks.append(_doctor_check_from_probe(label, result))
    return checks
