"""Classify Slack Web API errors that mean "this bot token no longer works".

A reinstall, an OAuth scope change, or someone revoking the app in Slack all
show up the same way: the next outbound call (a reply, a reaction, a Home
publish) fails with one of these codes. Distinguishing that from a transient
failure (rate limiting, a dropped connection) is what lets the UI show a
specific "reconnect" prompt instead of a generic error.
"""

from __future__ import annotations

# https://api.slack.com/authentication/oauth-v2#errors and the classic
# `auth.test`/`chat.postMessage` error codes that mean the token itself is
# dead, not just rate-limited or momentarily unreachable.
TOKEN_INVALID_ERRORS = frozenset(
    {
        "invalid_auth",
        "not_authed",
        "account_inactive",
        "token_revoked",
        "token_expired",
        "no_permission",
    }
)


def is_token_invalid_error(error: object) -> bool:
    """Whether a Slack Web API ``error`` code means the bot token is dead."""
    return str(error or "").strip().lower() in TOKEN_INVALID_ERRORS


def is_token_invalid_exception(exc: BaseException) -> bool:
    """Same check for an ``slack_sdk`` exception, matched by substring.

    ``SlackApiError`` stringifies with the error code embedded (e.g.
    ``"...the request to the Slack API failed. (error: invalid_auth)"``), so a
    substring match is simpler than reaching into ``exc.response``.
    """
    text = str(exc).lower()
    return any(marker in text for marker in TOKEN_INVALID_ERRORS)
