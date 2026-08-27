"""Resolve AWS Bedrock credentials for LangChain and boto3 (IAM-first)."""

from __future__ import annotations

import os
from typing import Any

DEFAULT_BEDROCK_REGION = "us-east-1"
DEFAULT_BEDROCK_MODEL = "us.anthropic.claude-sonnet-4-6"


def bedrock_region(config: Any | None = None) -> str:
    """Region for Bedrock control-plane and Converse calls."""
    configured = ""
    if config is not None:
        configured = str(config.get("llm.aws_region") or "").strip()
    env = (
        str(os.environ.get("AWS_REGION") or "").strip()
        or str(os.environ.get("AWS_DEFAULT_REGION") or "").strip()
    )
    return configured or env or DEFAULT_BEDROCK_REGION


def bedrock_profile(config: Any | None = None) -> str | None:
    """Optional named profile from Settings or ``AWS_PROFILE``."""
    configured = ""
    if config is not None:
        configured = str(config.get("llm.aws_profile") or "").strip()
    env = str(os.environ.get("AWS_PROFILE") or "").strip()
    return configured or env or None


def bedrock_explicit_keys(config: Any | None = None) -> tuple[str | None, str | None, str | None]:
    """Optional access-key override. Empty means use the IAM / profile chain."""
    def _get(config_key: str, env_name: str) -> str:
        raw = ""
        if config is not None:
            getter = getattr(config, "_normalized_secret", None)
            value = config.get(config_key)
            normalized = getter(value) if callable(getter) else value
            raw = str(normalized or "").strip()
        return raw or str(os.environ.get(env_name) or "").strip()

    access = _get("llm.aws_access_key_id", "AWS_ACCESS_KEY_ID")
    secret = _get("llm.aws_secret_access_key", "AWS_SECRET_ACCESS_KEY")
    token = _get("llm.aws_session_token", "AWS_SESSION_TOKEN")
    if access and secret:
        return access, secret, token or None
    return None, None, None


def bedrock_chat_kwargs(config: Any | None = None) -> dict[str, Any]:
    """Kwargs for ``ChatBedrockConverse`` — keys only when the user set them."""
    kwargs: dict[str, Any] = {"region_name": bedrock_region(config)}
    access, secret, token = bedrock_explicit_keys(config)
    if access and secret:
        kwargs["aws_access_key_id"] = access
        kwargs["aws_secret_access_key"] = secret
        if token:
            kwargs["aws_session_token"] = token
        return kwargs
    profile = bedrock_profile(config)
    if profile:
        kwargs["credentials_profile_name"] = profile
    return kwargs


def bedrock_boto3_client(service: str, config: Any | None = None):
    """Control-plane (``bedrock``) or runtime client using the same auth as LangChain."""
    import boto3

    region = bedrock_region(config)
    access, secret, token = bedrock_explicit_keys(config)
    if access and secret:
        return boto3.client(
            service,
            region_name=region,
            aws_access_key_id=access,
            aws_secret_access_key=secret,
            aws_session_token=token,
        )
    profile = bedrock_profile(config)
    session = boto3.Session(profile_name=profile, region_name=region)
    return session.client(service)
