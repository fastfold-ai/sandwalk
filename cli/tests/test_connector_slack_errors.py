"""Classifying Slack Web API failures that mean "reconnect this workspace"."""

from __future__ import annotations

from agent_server.connectors.slack_errors import (
    is_token_invalid_error,
    is_token_invalid_exception,
)


def test_recognizes_known_auth_failure_codes() -> None:
    for code in ("invalid_auth", "token_revoked", "account_inactive", "not_authed"):
        assert is_token_invalid_error(code) is True


def test_is_case_and_whitespace_insensitive() -> None:
    assert is_token_invalid_error("  Invalid_Auth  ") is True


def test_does_not_flag_transient_errors() -> None:
    for code in ("rate_limited", "not_in_channel", "channel_not_found", ""):
        assert is_token_invalid_error(code) is False


def test_none_is_not_a_failure() -> None:
    assert is_token_invalid_error(None) is False


def test_exception_matches_by_substring() -> None:
    exc = RuntimeError("SlackApiError: the request failed. (error: invalid_auth)")
    assert is_token_invalid_exception(exc) is True


def test_exception_without_a_known_code_is_not_flagged() -> None:
    exc = RuntimeError("connection reset by peer")
    assert is_token_invalid_exception(exc) is False
