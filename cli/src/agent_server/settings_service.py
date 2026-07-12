"""Runtime settings shared by terminal and web presentation layers."""

from agent.config import Config
from agent_server.models import RuntimeSettings, UpdateRuntimeSettingsRequest


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
        return SettingsService.get()
