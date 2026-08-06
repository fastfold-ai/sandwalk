"""Provider heal trusts storage — no catalog-prefix rewrites."""

from agent.config.profile_backend_infer import ProfileBackendInferMixin
from agent.config.profile_heal import ProfileHealMixin
from agent.model_catalog import catalog_providers_for_model


class _Heal(ProfileHealMixin, ProfileBackendInferMixin):
    """Stand-in for Config's heal + backend-infer mixins."""


def test_catalog_providers_for_model_lists_static_owners():
    assert "moonshot" in catalog_providers_for_model("kimi-k3")


def test_heal_trusts_stored_provider_for_shared_ids():
    for provider, model in (
        ("opencode", "kimi-k3"),
        ("openrouter", "anthropic/claude-sonnet-5"),
        ("moonshot", "kimi-k3"),
        ("qwen", "qwen3-max"),
    ):
        data = {"llm.provider": provider, "llm.model": model}
        healed, _active = _Heal._heal_profile_mismatches(
            data, {}, provider, model, "openai_cloud"
        )
        assert healed == provider
        assert data["llm.provider"] == provider


def test_heal_does_not_rewrite_gemini_under_openai():
    """Picker/config own provider — do not invent Google from a gemini-* id."""
    data = {"llm.provider": "openai", "llm.model": "gemini-3.5-flash"}
    provider, _active = _Heal._heal_profile_mismatches(
        data,
        {"openai_cloud": {"backend": "openai"}},
        "openai",
        "gemini-3.5-flash",
        "openai_cloud",
    )
    assert provider == "openai"
    assert data["llm.provider"] == "openai"


def test_heal_keeps_local_omlx_qwen_named_model():
    """Local GGUF ids like Qwen3.6-* must stay on the openai + oMLX profile."""
    model = "Qwen3.6-35B-A3B-OptiQ-4bit"
    profiles = {
        "omlx": {
            "backend": "omlx",
            "base_url": "http://localhost:8000/v1",
            "default_model": model,
        }
    }
    data = {"llm.provider": "openai", "llm.model": model}
    provider, active = _Heal._heal_profile_mismatches(
        data, profiles, "openai", model, "omlx"
    )
    assert provider == "openai"
    assert data["llm.provider"] == "openai"
    assert active == "omlx"
    assert data.get("llm.model") == model


def test_heal_does_not_touch_mismatched_cloud_provider_left_on_disk():
    """Broken legacy rows are not silently rewritten — re-select in /models."""
    model = "Qwen3.6-35B-A3B-OptiQ-4bit"
    profiles = {
        "omlx": {
            "backend": "omlx",
            "base_url": "http://localhost:8000/v1",
            "default_model": model,
        }
    }
    data = {"llm.provider": "qwen", "llm.model": model}
    provider, _active = _Heal._heal_profile_mismatches(
        data, profiles, "qwen", model, "omlx"
    )
    assert provider == "qwen"
    assert data["llm.provider"] == "qwen"


def test_heal_replaces_openai_cloud_model_on_local_backend():
    """GPT cloud ids cannot run on Ollama — fall back to the profile default."""
    profiles = {
        "ollama_local": {
            "backend": "ollama",
            "base_url": "http://localhost:11434/v1",
            "default_model": "llama3.1",
        }
    }
    data = {"llm.provider": "openai", "llm.model": "gpt-5.4"}
    provider, active = _Heal._heal_profile_mismatches(
        data, profiles, "openai", "gpt-5.4", "ollama_local"
    )
    assert provider == "openai"
    assert active == "ollama_local"
    assert data["llm.model"] == "llama3.1"
