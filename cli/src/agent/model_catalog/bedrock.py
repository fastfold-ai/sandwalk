"""Bedrock catalog helpers: chat-only filters and live list merge."""

from __future__ import annotations

from typing import Any

# Geo / system inference-profile prefixes (``us.anthropic.claude-…``).
_GEO_PREFIXES = frozenset({"us", "eu", "apac", "global", "jp", "au"})


def bedrock_bare_model_id(model_id: str | None) -> str:
    """Strip geo + vendor prefixes for heuristic matching."""
    value = str(model_id or "").strip().lower()
    if not value:
        return ""
    parts = value.split(".")
    if len(parts) >= 3 and parts[0] in _GEO_PREFIXES:
        return ".".join(parts[2:])
    if len(parts) >= 2 and parts[0] in {
        "anthropic",
        "amazon",
        "meta",
        "mistral",
        "cohere",
        "ai21",
        "stability",
        "qwen",
        "deepseek",
    }:
        return ".".join(parts[1:])
    return value


def is_chat_foundation_model(summary: dict[str, Any]) -> bool:
    """Keep TEXT chat models; drop embeddings, image-only, and LEGACY rows."""
    inputs = {str(item).upper() for item in (summary.get("inputModalities") or [])}
    outputs = {str(item).upper() for item in (summary.get("outputModalities") or [])}
    if "TEXT" not in inputs or "TEXT" not in outputs:
        return False
    if outputs == {"EMBEDDING"}:
        return False
    lifecycle = summary.get("modelLifecycle") or {}
    status = str(lifecycle.get("status") or "ACTIVE").upper()
    if status and status != "ACTIVE":
        return False
    return True


def inference_profile_id(profile: dict[str, Any]) -> str:
    return str(
        profile.get("inferenceProfileId")
        or profile.get("inferenceProfileName")
        or ""
    ).strip()


def merge_bedrock_catalog_ids(
    foundation_summaries: list[dict[str, Any]],
    inference_profiles: list[dict[str, Any]],
) -> list[str]:
    """Prefer inference-profile IDs when they map to a chat foundation model."""
    chat_foundation: dict[str, dict[str, Any]] = {}
    for summary in foundation_summaries:
        if not is_chat_foundation_model(summary):
            continue
        model_id = str(summary.get("modelId") or "").strip()
        if model_id:
            chat_foundation[model_id] = summary

    seen: set[str] = set()
    ordered: list[str] = []

    def _add(model_id: str) -> None:
        if model_id and model_id not in seen:
            seen.add(model_id)
            ordered.append(model_id)

    for profile in inference_profiles:
        profile_id = inference_profile_id(profile)
        if not profile_id:
            continue
        models = profile.get("models") or []
        if models:
            keep = False
            for item in models:
                mid = str((item or {}).get("modelArn") or (item or {}).get("modelId") or "")
                # ARN …/foundation-model/anthropic.claude-… or a bare id
                bare = mid.rsplit("/", 1)[-1]
                if bare in chat_foundation or any(
                    bare.endswith(fid) or fid.endswith(bare) for fid in chat_foundation
                ):
                    keep = True
                    break
            if not keep:
                continue
        _add(profile_id)

    for model_id in chat_foundation:
        _add(model_id)
    return ordered


def discover_bedrock_model_ids(config: Any | None = None) -> list[str]:
    """Live ``ListInferenceProfiles`` + ``ListFoundationModels`` (chat-only)."""
    from agent.config.bedrock_auth import bedrock_boto3_client

    client = bedrock_boto3_client("bedrock", config)
    foundations = client.list_foundation_models(byOutputModality="TEXT")
    summaries = list(foundations.get("modelSummaries") or [])
    profiles: list[dict[str, Any]] = []
    try:
        listed = client.list_inference_profiles()
        profiles = list(listed.get("inferenceProfileSummaries") or [])
    except Exception:  # noqa: BLE001 — catalog still useful without profiles
        profiles = []
    return merge_bedrock_catalog_ids(summaries, profiles)
