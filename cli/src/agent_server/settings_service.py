"""Runtime settings shared by terminal and web presentation layers."""

from agent.config import Config, sync_process_env_from_config
from agent_server.models import RuntimeSettings, UpdateRuntimeSettingsRequest

_DEFAULT_RECURSION_LIMIT = 120
_MIN_RECURSION_LIMIT = 25
_MAX_RECURSION_LIMIT = 2000


def _clamp_int(value: object, *, minimum: int, maximum: int, default: int) -> int:
    try:
        return max(minimum, min(maximum, int(value)))  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


def _recursion_limit_from_config(config: Config) -> int:
    raw = config.get("agent.recursion_limit")
    if raw is None or str(raw).strip() == "":
        max_turns = int(config.get("agent.max_sdk_turns", 30) or 30)
        return max(_MIN_RECURSION_LIMIT, max_turns * 2 + 10)
    return _clamp_int(
        raw,
        minimum=_MIN_RECURSION_LIMIT,
        maximum=_MAX_RECURSION_LIMIT,
        default=_DEFAULT_RECURSION_LIMIT,
    )


def _bool_from_config(config: Config, key: str, default: bool) -> bool:
    raw = config.get(key)
    if raw is None:
        return default
    if isinstance(raw, bool):
        return raw
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


class SettingsService:
    @staticmethod
    def get() -> RuntimeSettings:
        config = Config.load()
        return RuntimeSettings(
            provider=str(config.get("llm.provider") or "anthropic"),
            model=str(config.get("llm.model") or "claude-sonnet-4-5-20250929"),
            openai_base_url=str(config.get("llm.openai_base_url") or "").strip() or None,
            agent_profile=str(config.get("agent.profile") or "research"),
            tool_mode=str(config.get("agent.tool_mode") or "ptc"),
            recursion_limit=_recursion_limit_from_config(config),
            max_sdk_turns=_clamp_int(
                config.get("agent.max_sdk_turns", 30),
                minimum=1,
                maximum=500,
                default=30,
            ),
            group_tool_traces=_bool_from_config(
                config, "agent.group_tool_traces", True
            ),
            tool_trace_detail_limit=_clamp_int(
                config.get("agent.tool_trace_detail_limit", 1),
                minimum=1,
                maximum=50,
                default=1,
            ),
            background_watch_timeout_s=_clamp_int(
                config.get("agent.background_watch_timeout_s", 7200),
                minimum=60,
                maximum=86400,
                default=7200,
            ),
            interrupt_drain_timeout_s=_clamp_int(
                config.get("agent.interrupt_drain_timeout_s", 10),
                minimum=1,
                maximum=120,
                default=10,
            ),
            parallel_max_threads=_clamp_int(
                config.get("agent.parallel_max_threads", 5),
                minimum=1,
                maximum=20,
                default=5,
            ),
            tool_health_enabled=_bool_from_config(
                config, "agent.tool_health_enabled", True
            ),
            tool_health_fail_threshold=_clamp_int(
                config.get("agent.tool_health_fail_threshold", 2),
                minimum=1,
                maximum=20,
                default=2,
            ),
            tool_health_suppress_seconds=_clamp_int(
                config.get("agent.tool_health_suppress_seconds", 900),
                minimum=30,
                maximum=86400,
                default=900,
            ),
        )

    @staticmethod
    def update(payload: UpdateRuntimeSettingsRequest) -> RuntimeSettings:
        config = Config.load()
        # Apply everything except the model first. The model is set last so that
        # activating the OpenAI cloud profile (below) — which runs the config
        # auto-heal — cannot clobber a freshly-selected cloud model.
        non_model_updates = {
            "llm.provider": payload.provider,
            "llm.openai_base_url": payload.openai_base_url,
            "agent.profile": payload.agent_profile,
            "agent.tool_mode": payload.tool_mode,
        }
        for key, value in non_model_updates.items():
            if value is not None:
                config.set(key, value)

        if payload.recursion_limit is not None:
            config.set(
                "agent.recursion_limit",
                _clamp_int(
                    payload.recursion_limit,
                    minimum=_MIN_RECURSION_LIMIT,
                    maximum=_MAX_RECURSION_LIMIT,
                    default=_DEFAULT_RECURSION_LIMIT,
                ),
            )
        if payload.max_sdk_turns is not None:
            config.set(
                "agent.max_sdk_turns",
                _clamp_int(payload.max_sdk_turns, minimum=1, maximum=500, default=30),
            )
        if payload.group_tool_traces is not None:
            config.set("agent.group_tool_traces", bool(payload.group_tool_traces))
        if payload.tool_trace_detail_limit is not None:
            config.set(
                "agent.tool_trace_detail_limit",
                _clamp_int(
                    payload.tool_trace_detail_limit,
                    minimum=1,
                    maximum=50,
                    default=1,
                ),
            )
        if payload.background_watch_timeout_s is not None:
            config.set(
                "agent.background_watch_timeout_s",
                _clamp_int(
                    payload.background_watch_timeout_s,
                    minimum=60,
                    maximum=86400,
                    default=7200,
                ),
            )
        if payload.interrupt_drain_timeout_s is not None:
            config.set(
                "agent.interrupt_drain_timeout_s",
                _clamp_int(
                    payload.interrupt_drain_timeout_s,
                    minimum=1,
                    maximum=120,
                    default=10,
                ),
            )
        if payload.parallel_max_threads is not None:
            config.set(
                "agent.parallel_max_threads",
                _clamp_int(
                    payload.parallel_max_threads,
                    minimum=1,
                    maximum=20,
                    default=5,
                ),
            )
        if payload.tool_health_enabled is not None:
            config.set("agent.tool_health_enabled", bool(payload.tool_health_enabled))
        if payload.tool_health_fail_threshold is not None:
            config.set(
                "agent.tool_health_fail_threshold",
                _clamp_int(
                    payload.tool_health_fail_threshold,
                    minimum=1,
                    maximum=20,
                    default=2,
                ),
            )
        if payload.tool_health_suppress_seconds is not None:
            config.set(
                "agent.tool_health_suppress_seconds",
                _clamp_int(
                    payload.tool_health_suppress_seconds,
                    minimum=30,
                    maximum=86400,
                    default=900,
                ),
            )

        provider = str(config.get("llm.provider") or "").strip().lower()
        model = str(
            payload.model
            if payload.model is not None
            else (config.get("llm.model") or "")
        ).strip()

        # When switching to a cloud OpenAI model, activate the OpenAI cloud
        # profile BEFORE setting the model. Otherwise a previously-active local
        # profile (e.g. Ollama) stays active and the auto-heal reverts the cloud
        # model to the local one (cloud model + local endpoint is a mismatch).
        if provider == "openai" and model:
            custom_openai = {
                str(item.get("id"))
                for item in config.custom_models()
                if str(item.get("provider") or "").strip().lower() == "openai"
            }
            is_cloud_model = (
                Config._looks_like_openai_cloud_model(model) or model in custom_openai
            )
            if is_cloud_model:
                try:
                    config.set_openai_active_profile("openai_cloud")
                except Exception:
                    pass

        if payload.model is not None:
            config.set("llm.model", payload.model)

        config.save()
        # Keep process env aligned for settings-backed vars (do not clobber
        # unrelated shell-exported API keys).
        sync_process_env_from_config(
            config,
            only_missing=False,
            config_keys=[
                "llm.openai_base_url",
                "llm.provider",
                "llm.model",
                "data.base",
            ],
        )
        return SettingsService.get()
