"""Build the current RuntimeSettings snapshot from Config."""

from __future__ import annotations

from agent.config import Config
from agent.model_catalog import get_model_reasoning
from agent_server.file_access import normalize_file_access
from agent_server.models import RuntimeSettings
from agent_server.settings_service.limits import (
    bool_from_config,
    clamp_int,
    recursion_limit_from_config,
)


def get_runtime_settings(config: Config) -> RuntimeSettings:
    provider = str(config.get("llm.provider") or "openai")
    model = str(config.get("llm.model") or "gpt-5.6-sol")
    effort, fast = get_model_reasoning(
        config.get("llm.model_reasoning"),
        provider,
        model,
        default_effort=str(config.get("llm.reasoning_effort") or "medium"),
        default_fast=bool_from_config(config, "llm.reasoning_fast", False),
    )
    return RuntimeSettings(
        provider=provider,
        model=model,
        openai_base_url=str(config.get("llm.openai_base_url") or "").strip() or None,
        openai_profile_id=str(config.get("llm.openai_active_profile") or "").strip() or None,
        agent_profile=str(config.get("agent.profile") or "research"),
        tool_mode=str(config.get("agent.tool_mode") or "ptc"),
        knowledge_level=(
            str(config.get("agent.knowledge_level") or "high").strip().lower() or "high"
        ),
        reasoning_effort=effort,
        reasoning_fast=fast,
        recursion_limit=recursion_limit_from_config(config),
        max_sdk_turns=clamp_int(
            config.get("agent.max_sdk_turns", 30),
            minimum=1,
            maximum=500,
            default=30,
        ),
        group_tool_traces=bool_from_config(config, "agent.group_tool_traces", True),
        tool_trace_detail_limit=clamp_int(
            config.get("agent.tool_trace_detail_limit", 0),
            minimum=0,
            maximum=50,
            default=0,
        ),
        background_watch_timeout_s=clamp_int(
            config.get("agent.background_watch_timeout_s", 7200),
            minimum=60,
            maximum=86400,
            default=7200,
        ),
        interrupt_drain_timeout_s=clamp_int(
            config.get("agent.interrupt_drain_timeout_s", 10),
            minimum=1,
            maximum=120,
            default=10,
        ),
        parallel_max_threads=clamp_int(
            config.get("agent.parallel_max_threads", 5),
            minimum=1,
            maximum=20,
            default=5,
        ),
        tool_health_enabled=bool_from_config(config, "agent.tool_health_enabled", True),
        tool_health_fail_threshold=clamp_int(
            config.get("agent.tool_health_fail_threshold", 2),
            minimum=1,
            maximum=20,
            default=2,
        ),
        tool_health_suppress_seconds=clamp_int(
            config.get("agent.tool_health_suppress_seconds", 900),
            minimum=30,
            maximum=86400,
            default=900,
        ),
        plan_mode=bool_from_config(config, "agent.plan_preview", False),
        file_access=normalize_file_access(config.get("agent.file_access")),
        max_concurrent_runs=clamp_int(
            config.get("agent.max_concurrent_runs", 0),
            minimum=0,
            maximum=64,
            default=0,
        ),
        min_free_memory_mb=clamp_int(
            config.get("agent.min_free_memory_mb", 2048),
            minimum=0,
            maximum=262_144,
            default=2048,
        ),
    )
