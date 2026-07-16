"""Model catalog + OpenAI-compatible profile management for the agent server.

Split package — re-exports the public surface previously defined in
``agent_server/models_service.py`` so existing imports keep working.
"""

from __future__ import annotations

from agent.config import Config
from agent.model_discovery import probe_compatible_profile
from agent_server.models import (
    AgentModel,
    AgentModelList,
    CreateAgentModelRequest,
    ModelProfile,
    ModelProfileList,
    ModelProfileProbeResult,
    UpdateAgentModelRequest,
    UpsertModelProfileRequest,
)
from agent_server.models_service.catalog import list_models as _list_models
from agent_server.models_service.mutate import (
    create_custom_model as _create_custom_model,
)
from agent_server.models_service.mutate import (
    delete_custom_model as _delete_custom_model,
)
from agent_server.models_service.mutate import (
    set_model_enabled as _set_model_enabled,
)
from agent_server.models_service.mutate import (
    update_model as _update_model,
)
from agent_server.models_service.profiles import delete_profile as _delete_profile
from agent_server.models_service.profiles import discover_endpoint as _discover_endpoint
from agent_server.models_service.profiles import get_profile as _get_profile
from agent_server.models_service.profiles import list_profiles as _list_profiles
from agent_server.models_service.profiles import probe_profile as _probe_profile
from agent_server.models_service.profiles import upsert_profile as _upsert_profile

__all__ = ["ModelsService"]


class ModelsService:
    def list_models(
        self, *, enabled_only: bool = False, discover: bool = True
    ) -> AgentModelList:
        return _list_models(Config.load(), enabled_only=enabled_only, discover=discover)

    def set_model_enabled(self, model_id: str, enabled: bool) -> AgentModel:
        return _set_model_enabled(model_id, enabled)

    def create_custom_model(self, payload: CreateAgentModelRequest) -> AgentModel:
        return _create_custom_model(payload)

    def delete_custom_model(self, model_id: str) -> bool:
        return _delete_custom_model(model_id)

    def update_model(self, model_id: str, payload: UpdateAgentModelRequest) -> AgentModel:
        return _update_model(model_id, payload)

    def list_profiles(self, *, include_cloud: bool = True) -> ModelProfileList:
        return _list_profiles(Config.load(), include_cloud=include_cloud)

    def get_profile(self, profile_id: str) -> ModelProfile | None:
        return _get_profile(Config.load(), profile_id)

    def upsert_profile(self, payload: UpsertModelProfileRequest) -> ModelProfile:
        return _upsert_profile(Config.load(), payload)

    def delete_profile(self, profile_id: str) -> bool:
        return _delete_profile(Config.load(), profile_id)

    def probe_profile(self, profile_id: str) -> ModelProfileProbeResult:
        return _probe_profile(Config.load(), profile_id)

    def discover_endpoint(
        self,
        *,
        backend: str,
        base_url: str,
        api_key: str | None = None,
        profile_id: str = "preview",
    ) -> ModelProfileProbeResult:
        return _discover_endpoint(
            backend=backend, base_url=base_url, api_key=api_key, profile_id=profile_id
        )
