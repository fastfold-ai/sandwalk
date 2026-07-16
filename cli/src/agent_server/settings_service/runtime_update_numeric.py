"""Apply the numeric/boolean scalar runtime-settings fields."""

from __future__ import annotations

from agent.config import Config
from agent_server.models import UpdateRuntimeSettingsRequest
from agent_server.settings_service.limits import (
    DEFAULT_RECURSION_LIMIT,
    MAX_RECURSION_LIMIT,
    MIN_RECURSION_LIMIT,
    clamp_int,
)


def apply_numeric_updates(config: Config, payload: UpdateRuntimeSettingsRequest) -> None:
    if payload.recursion_limit is not None:
        config.set(
            "agent.recursion_limit",
            clamp_int(
                payload.recursion_limit,
                minimum=MIN_RECURSION_LIMIT,
                maximum=MAX_RECURSION_LIMIT,
                default=DEFAULT_RECURSION_LIMIT,
            ),
        )
    if payload.max_sdk_turns is not None:
        config.set(
            "agent.max_sdk_turns",
            clamp_int(payload.max_sdk_turns, minimum=1, maximum=500, default=30),
        )
    if payload.group_tool_traces is not None:
        config.set("agent.group_tool_traces", bool(payload.group_tool_traces))
    if payload.tool_trace_detail_limit is not None:
        config.set(
            "agent.tool_trace_detail_limit",
            clamp_int(payload.tool_trace_detail_limit, minimum=1, maximum=50, default=1),
        )
    if payload.background_watch_timeout_s is not None:
        config.set(
            "agent.background_watch_timeout_s",
            clamp_int(
                payload.background_watch_timeout_s,
                minimum=60,
                maximum=86400,
                default=7200,
            ),
        )
    if payload.interrupt_drain_timeout_s is not None:
        config.set(
            "agent.interrupt_drain_timeout_s",
            clamp_int(payload.interrupt_drain_timeout_s, minimum=1, maximum=120, default=10),
        )
    if payload.parallel_max_threads is not None:
        config.set(
            "agent.parallel_max_threads",
            clamp_int(payload.parallel_max_threads, minimum=1, maximum=20, default=5),
        )
    if payload.tool_health_enabled is not None:
        config.set("agent.tool_health_enabled", bool(payload.tool_health_enabled))
    if payload.tool_health_fail_threshold is not None:
        config.set(
            "agent.tool_health_fail_threshold",
            clamp_int(payload.tool_health_fail_threshold, minimum=1, maximum=20, default=2),
        )
    if payload.tool_health_suppress_seconds is not None:
        config.set(
            "agent.tool_health_suppress_seconds",
            clamp_int(
                payload.tool_health_suppress_seconds,
                minimum=30,
                maximum=86400,
                default=900,
            ),
        )
