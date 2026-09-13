"""Offline mode detection and graceful degradation for sandwalk.

This module provides:
- Automatic network health detection on startup and periodically.
- A global ``is_offline`` flag that controls graceful degradation.
- Helper functions to skip or degrade network-dependent features.
- CLI integration via ``--offline`` flag or ``SANDWALK_OFFLINE`` env var.

When offline:
- Slack connectors skip startup silently (no noisy errors).
- AWS credential refresh is skipped.
- Modal sandbox falls back to builtin FilesystemBackend.
- MCP OAuth token refreshes are skipped (existing tokens still work).
- Model probing stays local (no cloud model catalog checks).
- A subtle offline banner shows in the UI.
"""

from __future__ import annotations

import asyncio
import logging
import os
import socket
from datetime import UTC, datetime, timedelta, timezone
from typing import Any

logger = logging.getLogger("agent_server.offline_mode")

# DNS hosts to probe for connectivity. We pick diverse, always-up DNS names
# to minimize false negatives while avoiding overloading any single resolver.
_DEFAULT_DNS_PROBE_TARGETS = [
    "slack.com",
    "sts.amazonaws.com",
    "modal.com",
    "registry.huggingface.co",
]


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

def _force_offline() -> bool:
    """Return True if the user explicitly forced offline mode."""
    # CLI flag sets this env var
    return os.environ.get("SANDWALK_FORCE_OFFLINE") == "1"


def _offline_checks_disabled() -> bool:
    """Return True to skip all network checks (quiet mode)."""
    return os.environ.get("SANDWALK_SILENT_OFFLINE") == "1"


# ---------------------------------------------------------------------------
# Global state
# ---------------------------------------------------------------------------

_offline: bool = False
_offline_reason: str | None = None
_last_check_time: datetime | None = None
_last_check_targets: list[str] | None = None
_probe_targets: list[str] = list(_DEFAULT_DNS_PROBE_TARGETS)


def get_offline_state() -> dict[str, Any]:
    """Return the current offline state for API/UI consumption."""
    return {
        "is_offline": _offline,
        "reason": _offline_reason,
        "last_check": _last_check_time.isoformat() if _last_check_time else None,
        "targets_checked": _last_check_targets,
        "forced": _force_offline(),
        "manual_override": os.environ.get("SANDWALK_FORCE_OFFLINE"),
    }


def is_offline() -> bool:
    """Check whether the server considers itself offline.

    This is the primary function used by other modules to decide whether to
    skip network-dependent operations. It checks both the forced mode and the
    health detection state.
    """
    if _force_offline():
        return True
    if _offline_checks_disabled():
        return False
    # Re-check if it's been more than 30 seconds since last probe
    if _last_check_time is None or (datetime.now(UTC) - _last_check_time) > timedelta(seconds=30):
        _check_network_health()
    return _offline


def get_offline_reason() -> str | None:
    """Return the reason we believe we're offline, if known."""
    return _offline_reason


def get_ui_status() -> dict[str, Any]:
    """Return status data for the UI offline banner."""
    state = get_offline_state()
    return {
        **state,
        # Simplified message for UI
        "message": _get_offline_message(),
        "features_affected": _get_affected_features(),
    }


def _get_offline_message() -> str:
    """Get a user-friendly message about offline status."""
    if _force_offline():
        return "Running in offline mode"
    if _offline:
        if _offline_reason == "force_offline":
            return "Running in offline mode"
        elif _offline_reason:
            return f"Offline — {_offline_reason}"
        return "Offline — some features may not work"
    return ""


def _get_affected_features() -> list[str]:
    """List features that are degraded due to offline status."""
    features = []
    if _offline:
        features = [
            "Slack connectors (inbound/outbound messages)",
            "Cloud model catalog",
            "MCP OAuth token refresh",
            "AWS credential refresh",
            "Modal sandbox (uses local filesystem instead)",
            "External MCP tool loading",
            "Model health checks",
        ]
    return features


# ---------------------------------------------------------------------------
# Network health detection
# ---------------------------------------------------------------------------

def _check_network_health() -> None:
    """Probe DNS for a set of targets. Sets ``_offline`` and ``_offline_reason``."""
    global _offline, _offline_reason, _last_check_time, _last_check_targets

    if _force_offline():
        _offline = True
        _offline_reason = "force_offline"
        _last_check_time = datetime.now(UTC)
        _last_check_targets = _probe_targets
        return

    if _offline_checks_disabled():
        _offline = False
        _offline_reason = None
        _last_check_time = datetime.now(UTC)
        _last_check_targets = []
        return

    successful_targets = []
    failed_targets = []

    for host in _probe_targets:
        try:
            # Use a non-blocking DNS lookup
            result = socket.getaddrinfo(host, None, socket.AF_INET, socket.SOCK_STREAM)
            if result:
                successful_targets.append(host)
            else:
                failed_targets.append(host)
        except (socket.gaierror, socket.herror, OSError):
            failed_targets.append(host)
        except Exception:
            failed_targets.append(host)

    _last_check_time = datetime.now(UTC)
    _last_check_targets = _probe_targets

    # We're offline if majority of targets fail
    total = len(_probe_targets)
    if total == 0:
        _offline = False
        _offline_reason = None
        return

    failure_rate = len(failed_targets) / total

    if failure_rate >= 0.5:
        _offline = True
        if failed_targets:
            _offline_reason = f"{len(failed_targets)}/{total} targets unreachable ({', '.join(failed_targets[:3])})"
        else:
            _offline_reason = "all targets unreachable"
        logger.info("Offline mode activated: %s", _offline_reason)
    else:
        _offline = False
        _offline_reason = None


async def check_network_health_async() -> bool:
    """Async version of network health check. Returns True if online."""
    _check_network_health()
    return not _offline


def set_probe_targets(targets: list[str]) -> None:
    """Override the default DNS probe targets (for testing or custom setups)."""
    global _probe_targets
    _probe_targets = targets


def force_offline(force: bool = True, reason: str | None = None) -> None:
    """Programmatically set offline mode (for testing or admin override)."""
    global _offline, _offline_reason
    if force:
        _offline = True
        _offline_reason = reason or "force_offline"
        _last_check_time = datetime.now(UTC)
    else:
        _offline = False
        _offline_reason = None


# ---------------------------------------------------------------------------
# Graceful degradation helpers
# ---------------------------------------------------------------------------

def skip_if_offline(default: Any = None) -> Any:
    """Decorator-like helper to skip an operation when offline.

    Usage:
        if skip_if_offline():
            return default_response
        # ... normal operation
    """
    if is_offline():
        return True  # Signal to skip
    return False


def should_use_builtin_sandbox() -> bool:
    """Return True if we should use the builtin sandbox (not Modal).

    This is called during sandbox resolution to auto-select the local
    backend when network is unavailable.
    """
    return is_offline() or _force_offline()


def should_skip_slack_connectors() -> bool:
    """Return True if Slack connector startup should be skipped."""
    return is_offline()


def should_skip_mcp_oauth_refresh() -> bool:
    """Return True if MCP OAuth token refresh should be skipped."""
    return is_offline()


def should_skip_aws_credential_refresh() -> bool:
    """Return True if AWS credential refresh should be skipped."""
    return is_offline()


def should_skip_cloud_model_probes() -> bool:
    """Return True if cloud model catalog probes should be skipped."""
    return is_offline()


# ---------------------------------------------------------------------------
# Startup integration
# ---------------------------------------------------------------------------

async def init_offline_mode() -> None:
    """Initialize offline mode detection on server startup.

    This runs the initial network health check and sets the global state.
    It is non-blocking — the check happens in a background task that polls
    periodically.
    """
    # Run initial check
    _check_network_health()

    if _offline:
        logger.info(
            "Sandwalk starting in offline mode: %s", _offline_reason or "network unreachable"
        )
        logger.info(
            "Local features (agent, sandbox, sessions) will work normally. "
            "Cloud features (Slack, Modal sandbox, MCP OAuth) are unavailable."
        )
    else:
        logger.info("Network health check passed — online mode active")


async def start_offline_periodic_checks() -> None:
    """Start periodic network health checks (runs until server shuts down).

    Checks every 30 seconds. In offline mode, re-checks more frequently
    (every 10 seconds) to detect when connectivity is restored.
    """
    interval = 10.0 if _offline else 30.0

    while True:
        await asyncio.sleep(interval)
        old_offline = _offline
        _check_network_health()

        # Log if we transitioned from offline to online
        if old_offline and not _offline:
            logger.info("Network connectivity restored — resuming cloud features")

        # Adjust interval based on current state
        if _offline:
            interval = 10.0
        else:
            interval = 30.0


def is_feature_available(feature: str) -> bool:
    """Check if a specific feature is available in the current mode.

    Args:
        feature: One of 'slack', 'modal', 'mcp_oauth', 'aws_creds',
                 'cloud_models', 'mcp_tools', 'model_probes'

    Returns:
        True if the feature is available, False if offline/degraded.
    """
    if not is_offline():
        return True

    unavailable = {
        "slack": True,
        "modal": True,
        "mcp_oauth": True,
        "aws_creds": True,
        "cloud_models": True,
        "mcp_tools": True,
        "model_probes": True,
    }

    return not unavailable.get(feature, False)


def get_degraded_features() -> list[str]:
    """Return a list of feature names that are degraded/available locally."""
    if not is_offline():
        return []

    degraded = {
        "slack": "Slack connectors",
        "modal": "Modal sandbox",
        "mcp_oauth": "MCP OAuth refresh",
        "aws_creds": "AWS credential refresh",
        "cloud_models": "Cloud model catalog",
        "mcp_tools": "External MCP tools",
        "model_probes": "Cloud model probes",
    }

    return [degraded[k] for k in degraded]
