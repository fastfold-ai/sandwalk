"""Same model ids can be hosted by multiple providers — heal must respect that."""

from agent.config.profile_heal import ProfileHealMixin
from agent.model_catalog import catalog_providers_for_model


def test_catalog_providers_for_model_lists_static_owners():
    assert "moonshot" in catalog_providers_for_model("kimi-k3")


def test_heal_keeps_opencode_for_kimi_k3():
    data = {"llm.provider": "opencode", "llm.model": "kimi-k3"}
    provider, _active = ProfileHealMixin._heal_profile_mismatches(
        data, {}, "opencode", "kimi-k3", "openai_cloud"
    )
    assert provider == "opencode"
    assert data["llm.provider"] == "opencode"


def test_heal_keeps_openrouter_for_shared_ids():
    data = {
        "llm.provider": "openrouter",
        "llm.model": "anthropic/claude-sonnet-5",
    }
    provider, _active = ProfileHealMixin._heal_profile_mismatches(
        data, {}, "openrouter", "anthropic/claude-sonnet-5", "openai_cloud"
    )
    assert provider == "openrouter"
    assert data["llm.provider"] == "openrouter"


def test_heal_keeps_moonshot_native_kimi():
    data = {"llm.provider": "moonshot", "llm.model": "kimi-k3"}
    provider, _active = ProfileHealMixin._heal_profile_mismatches(
        data, {}, "moonshot", "kimi-k3", "openai_cloud"
    )
    assert provider == "moonshot"
    assert data["llm.provider"] == "moonshot"


def test_heal_still_rewrites_gemini_under_openai():
    data = {"llm.provider": "openai", "llm.model": "gemini-3.5-flash"}
    provider, _active = ProfileHealMixin._heal_profile_mismatches(
        data,
        {"openai_cloud": {"backend": "openai"}},
        "openai",
        "gemini-3.5-flash",
        "openai_cloud",
    )
    assert provider == "google"
    assert data["llm.provider"] == "google"


def test_provider_hosts_model_discovery_and_catalog():
    assert ProfileHealMixin._provider_hosts_model("opencode", "kimi-k3")
    assert ProfileHealMixin._provider_hosts_model("opencode", "gpt-5.4")
    assert ProfileHealMixin._provider_hosts_model("moonshot", "kimi-k3")
    assert ProfileHealMixin._provider_hosts_model("openrouter", "anything/goes")
    assert not ProfileHealMixin._provider_hosts_model("google", "kimi-k3")
    assert not ProfileHealMixin._provider_hosts_model("openai", "gemini-3.5-flash")
