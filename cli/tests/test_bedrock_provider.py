"""Amazon Bedrock catalog, IAM-default chat dispatch, and chat-only filters."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from agent.config import API_KEYS, VALID_LLM_PROVIDERS
from agent.config.bedrock_auth import bedrock_chat_kwargs
from agent.model_catalog import AVAILABLE_MODELS, catalog_provider_for_model
from agent.model_catalog.bedrock import (
    is_chat_foundation_model,
    merge_bedrock_catalog_ids,
)
from cli.setup.providers import _parse_provider_list


def test_bedrock_in_catalog_and_allowlist():
    rows = AVAILABLE_MODELS.get("bedrock") or []
    ids = {row[0] for row in rows}
    assert "us.anthropic.claude-sonnet-4-6" in ids
    assert "us.amazon.nova-pro-v1:0" in ids
    assert "bedrock" in VALID_LLM_PROVIDERS
    assert API_KEYS["llm.aws_region"]["env_var"] == "AWS_REGION"
    assert API_KEYS["llm.aws_region"]["secret"] is False
    assert API_KEYS["llm.aws_profile"]["provider_key"] == "bedrock"
    assert API_KEYS["llm.aws_access_key_id"]["provider_key"] == "bedrock"
    assert catalog_provider_for_model("us.anthropic.claude-sonnet-4-6") == "bedrock"
    assert _parse_provider_list("bedrock,aws") == ["bedrock"]


class _Cfg:
    def __init__(self, data: dict):
        self._data = data

    def get(self, key, default=None):
        return self._data.get(key, default)

    def _normalized_secret(self, value):
        return value


def test_bedrock_chat_kwargs_omit_keys_for_iam_default():
    cfg = _Cfg(
        {
            "llm.aws_region": "us-west-2",
            "llm.aws_profile": "research",
            "llm.aws_access_key_id": None,
            "llm.aws_secret_access_key": None,
            "llm.aws_session_token": None,
        }
    )

    env_patch = {
        "AWS_ACCESS_KEY_ID": "",
        "AWS_SECRET_ACCESS_KEY": "",
        "AWS_SESSION_TOKEN": "",
        "AWS_PROFILE": "",
        "AWS_REGION": "",
        "AWS_DEFAULT_REGION": "",
    }
    with patch.dict("os.environ", env_patch, clear=False):
        kwargs = bedrock_chat_kwargs(cfg)
    assert kwargs["region_name"] == "us-west-2"
    assert kwargs["credentials_profile_name"] == "research"
    assert "aws_access_key_id" not in kwargs
    assert "aws_secret_access_key" not in kwargs


def test_bedrock_chat_kwargs_pass_explicit_keys_only_when_set():
    cfg = _Cfg(
        {
            "llm.aws_region": "us-east-1",
            "llm.aws_profile": "ignored-when-keys-set",
            "llm.aws_access_key_id": "AKIATEST",
            "llm.aws_secret_access_key": "secret",
            "llm.aws_session_token": "token",
        }
    )

    kwargs = bedrock_chat_kwargs(cfg)
    assert kwargs["aws_access_key_id"] == "AKIATEST"
    assert kwargs["aws_secret_access_key"] == "secret"
    assert kwargs["aws_session_token"] == "token"
    assert "credentials_profile_name" not in kwargs


def test_build_chat_model_dispatches_to_bedrock():
    from agent.deepagents_runtime.chat_model import build_chat_model

    cfg = MagicMock()
    cfg.get.side_effect = lambda key, default=None: {
        "llm.provider": "bedrock",
        "llm.model": "us.anthropic.claude-sonnet-4-6",
        "llm.temperature": 0.1,
    }.get(key, default)

    with patch(
        "agent.deepagents_runtime.chat_model.build_bedrock_chat_model",
        return_value="bedrock-model",
    ) as mock_build:
        result = build_chat_model(cfg)
        assert result == "bedrock-model"
        mock_build.assert_called_once()


def test_build_bedrock_chat_model_iam_default_kwargs():
    from agent.deepagents_runtime.chat_model_bedrock import build_bedrock_chat_model

    cfg = _Cfg(
        {
            "llm.model": "us.anthropic.claude-sonnet-4-6",
            "llm.aws_region": "eu-west-1",
            "llm.aws_profile": "lab",
            "llm.aws_access_key_id": None,
            "llm.aws_secret_access_key": None,
            "llm.aws_session_token": None,
        }
    )

    env_patch = {
        "AWS_ACCESS_KEY_ID": "",
        "AWS_SECRET_ACCESS_KEY": "",
        "AWS_SESSION_TOKEN": "",
        "AWS_PROFILE": "",
        "AWS_REGION": "",
        "AWS_DEFAULT_REGION": "",
    }
    with patch.dict("os.environ", env_patch, clear=False), patch(
        "langchain_aws.ChatBedrockConverse",
        return_value=MagicMock(name="chat"),
    ) as mock_cls:
        build_bedrock_chat_model(cfg, temperature=0.2)
        kwargs = mock_cls.call_args.kwargs
        assert kwargs["model"] == "us.anthropic.claude-sonnet-4-6"
        assert kwargs["region_name"] == "eu-west-1"
        assert kwargs["credentials_profile_name"] == "lab"
        assert "aws_access_key_id" not in kwargs


def test_bedrock_catalog_filter_keeps_chat_drops_embeddings():
    foundations = [
        {
            "modelId": "amazon.titan-embed-text-v2:0",
            "inputModalities": ["TEXT"],
            "outputModalities": ["EMBEDDING"],
            "modelLifecycle": {"status": "ACTIVE"},
        },
        {
            "modelId": "anthropic.claude-sonnet-4-6",
            "inputModalities": ["TEXT"],
            "outputModalities": ["TEXT"],
            "modelLifecycle": {"status": "ACTIVE"},
        },
        {
            "modelId": "stability.stable-image",
            "inputModalities": ["TEXT"],
            "outputModalities": ["IMAGE"],
            "modelLifecycle": {"status": "ACTIVE"},
        },
        {
            "modelId": "anthropic.claude-legacy",
            "inputModalities": ["TEXT"],
            "outputModalities": ["TEXT"],
            "modelLifecycle": {"status": "LEGACY"},
        },
    ]
    profiles = [
        {
            "inferenceProfileId": "us.anthropic.claude-sonnet-4-6",
            "models": [{"modelId": "anthropic.claude-sonnet-4-6"}],
        }
    ]
    assert is_chat_foundation_model(foundations[1]) is True
    assert is_chat_foundation_model(foundations[0]) is False
    merged = merge_bedrock_catalog_ids(foundations, profiles)
    assert "us.anthropic.claude-sonnet-4-6" in merged
    assert "anthropic.claude-sonnet-4-6" in merged
    assert "amazon.titan-embed-text-v2:0" not in merged
    assert "stability.stable-image" not in merged
    assert "anthropic.claude-legacy" not in merged
