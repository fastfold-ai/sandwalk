"""Tests for configuration loading, LLM preflight validation, and schema validation."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from agent import config as config_mod
from agent.config import Config, _validate_config


def test_load_invalid_json_does_not_crash(monkeypatch, tmp_path):
    bad_config = tmp_path / "config.json"
    bad_backup = tmp_path / "config.json.bak"
    bad_config.write_text("{ not valid json")

    monkeypatch.setattr(config_mod, "CONFIG_FILE", bad_config)
    monkeypatch.setattr(config_mod, "CONFIG_BACKUP_FILE", bad_backup)

    cfg = Config.load()
    # Should fall back to defaults when config file is corrupt
    assert cfg.get("llm.provider") == "anthropic"


def test_load_recovers_from_backup_when_primary_is_corrupt(monkeypatch, tmp_path):
    bad_config = tmp_path / "config.json"
    backup_config = tmp_path / "config.json.bak"
    bad_config.write_text("{ not valid json")
    backup_config.write_text(json.dumps({"llm.provider": "openai", "llm.model": "gpt-5.5"}))

    monkeypatch.setattr(config_mod, "CONFIG_FILE", bad_config)
    monkeypatch.setattr(config_mod, "CONFIG_BACKUP_FILE", backup_config)

    cfg = Config.load()
    assert cfg.get("llm.provider") == "openai"
    restored = json.loads(bad_config.read_text())
    assert restored["llm.provider"] == "openai"


def test_llm_preflight_requires_anthropic_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_FOUNDRY_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_FOUNDRY_RESOURCE", raising=False)
    cfg = Config(data={"llm.provider": "anthropic"})
    issue = cfg.llm_preflight_issue()
    assert issue is not None
    assert "Anthropic API key" in issue


def test_llm_preflight_accepts_foundry_env_vars(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("ANTHROPIC_FOUNDRY_API_KEY", "test-key")
    monkeypatch.setenv("ANTHROPIC_FOUNDRY_RESOURCE", "test-resource")
    cfg = Config(data={"llm.provider": "anthropic"})
    assert cfg.llm_preflight_issue() is None


def test_llm_preflight_error_mentions_foundry(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_FOUNDRY_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_FOUNDRY_RESOURCE", raising=False)
    cfg = Config(data={"llm.provider": "anthropic"})
    issue = cfg.llm_preflight_issue()
    assert "Foundry" in issue


def test_llm_preflight_requires_openai_key():
    cfg = Config(data={"llm.provider": "openai"})
    issue = cfg.llm_preflight_issue()
    assert issue is not None
    assert "OpenAI API key" in issue


def test_llm_preflight_allows_local_openai_base_url_without_key():
    cfg = Config(
        data={
            "llm.provider": "openai",
            "llm.model": "llama3.1",
            "llm.openai_base_url": "http://localhost:11434/v1",
            "llm.openai_api_key": None,
        }
    )
    assert cfg.llm_preflight_issue() is None


def test_llm_preflight_requires_key_for_non_local_openai_base_url():
    cfg = Config(
        data={
            "llm.provider": "openai",
            "llm.model": "gpt-5.5",
            "llm.openai_base_url": "https://api.openai.com/v1",
            "llm.openai_api_key": None,
        }
    )
    issue = cfg.llm_preflight_issue()
    assert issue is not None
    assert "OpenAI API key" in issue


def test_llm_preflight_allows_custom_remote_openai_compatible_without_key():
    cfg = Config(
        data={
            "llm.provider": "openai",
            "llm.model": "qwen3.6:27b",
            "llm.openai_base_url": "http://ai-server.tail9762ec.ts.net:11434/v1",
            "llm.openai_api_key": None,
        }
    )
    assert cfg.llm_preflight_issue() is None


def test_llm_preflight_accepts_openai_key():
    cfg = Config(
        data={
            "llm.provider": "openai",
            "llm.openai_api_key": "test-openai-key",
            "llm.model": "gpt-4o",
        }
    )
    assert cfg.llm_preflight_issue() is None


def test_llm_preflight_openai_does_not_use_anthropic_key_fallback():
    cfg = Config(
        data={
            "llm.provider": "openai",
            "llm.api_key": "sk-ant-some-anthropic-key",
            "llm.openai_api_key": None,
        }
    )
    issue = cfg.llm_preflight_issue()
    assert issue is not None
    assert "OpenAI API key" in issue


def test_llm_preflight_openai_rejects_anthropic_like_key():
    cfg = Config(
        data={
            "llm.provider": "openai",
            "llm.openai_api_key": "sk-ant-api03-looks-like-anthropic",
        }
    )
    issue = cfg.llm_preflight_issue()
    assert issue is not None
    assert "appears to be an Anthropic key" in issue


def test_llm_preflight_openai_whitespace_key_treated_as_missing():
    cfg = Config(
        data={
            "llm.provider": "openai",
            "llm.openai_api_key": "   ",
        }
    )
    issue = cfg.llm_preflight_issue()
    assert issue is not None
    assert "OpenAI API key" in issue


def test_llm_preflight_openai_control_sequence_key_treated_as_missing():
    cfg = Config(
        data={
            "llm.provider": "openai",
            "llm.openai_api_key": "\x1b[42;52R\x03\x03\x03",
        }
    )
    issue = cfg.llm_preflight_issue()
    assert issue is not None
    assert "OpenAI API key" in issue


def test_llm_api_key_prefers_new_anthropic_key():
    cfg = Config(
        data={
            "llm.provider": "anthropic",
            "llm.anthropic_api_key": "new-anthropic-key",
            "llm.api_key": "legacy-anthropic-key",
        }
    )
    assert cfg.llm_api_key("anthropic") == "new-anthropic-key"


def test_infer_openai_compatible_backend_new_template_ports():
    assert Config.infer_openai_compatible_backend("http://localhost:1234/v1") == "lm_studio"
    assert Config.infer_openai_compatible_backend("http://localhost:8080/v1") == "llama_cpp"
    assert Config.infer_openai_compatible_backend("http://localhost:8000/v1/ds4") == "ds4"


def test_set_openai_compatible_backend_normalizes_aliases():
    cfg = Config(data={"llm.openai_base_url": "http://localhost:1234/v1"})
    cfg.set("llm.openai_compatible_backend", "lmstudio")
    assert cfg.get("llm.openai_compatible_backend") == "lm_studio"


def test_llm_api_key_legacy_fallback_for_anthropic():
    cfg = Config(
        data={
            "llm.provider": "anthropic",
            "llm.api_key": "legacy-anthropic-key",
        }
    )
    assert cfg.llm_api_key("anthropic") == "legacy-anthropic-key"


def test_keys_table_includes_llm_provider_keys():
    cfg = Config(data={})
    table = cfg.keys_table()
    first_col = list(getattr(table.columns[0], "_cells", []))
    assert "Anthropic" in first_col
    assert "OpenAI" in first_col


def test_keys_table_includes_boltz_provider():
    cfg = Config(data={"api.boltz_api_key": "sk_bc_test_1234567890"})
    table = cfg.keys_table()
    services = list(getattr(table.columns[0], "_cells", []))
    previews = list(getattr(table.columns[2], "_cells", []))
    assert "Boltz" in services
    boltz_idx = services.index("Boltz")
    assert previews[boltz_idx].startswith("sk_bc_te")
    assert "..." in previews[boltz_idx]


def test_keys_table_includes_preview_column_and_masked_openai_value():
    cfg = Config(data={"llm.openai_api_key": "sk-proj-AbCdEf1234567890xyz"})
    table = cfg.keys_table()
    headers = [getattr(col, "header", "") for col in table.columns]
    assert "Preview" in headers
    services = list(getattr(table.columns[0], "_cells", []))
    openai_idx = services.index("OpenAI")
    preview_col = list(getattr(table.columns[2], "_cells", []))
    assert preview_col[openai_idx].startswith("sk-proj-")
    assert "..." in preview_col[openai_idx]


def test_keys_table_lists_compatible_profiles_dynamically():
    cfg = Config(data={"llm.provider": "openai"})
    cfg.upsert_openai_profile(
        profile_id="omlx_local",
        label="oMLX Local",
        backend="omlx",
        base_url="http://localhost:8000/v1",
        api_key="sk-omlx-example",
        set_active=True,
    )
    cfg.upsert_openai_profile(
        profile_id="unsloth_lab",
        label="Unsloth Lab",
        backend="unsloth",
        base_url="http://localhost:8888/v1",
        api_key=None,
    )

    table = cfg.keys_table()
    service_col = list(getattr(table.columns[0], "_cells", []))
    status_col = list(getattr(table.columns[1], "_cells", []))
    unlocks_col = list(getattr(table.columns[3], "_cells", []))

    assert "OpenAI-compatible: oMLX Local" in service_col
    assert "OpenAI-compatible: Unsloth Lab" in service_col

    omlx_idx = service_col.index("OpenAI-compatible: oMLX Local")
    unsloth_idx = service_col.index("OpenAI-compatible: Unsloth Lab")
    assert "configured" in status_col[omlx_idx]
    assert "active" in status_col[omlx_idx]
    assert "not set" in status_col[unsloth_idx]
    assert "omlx endpoint" in unlocks_col[omlx_idx]
    assert "unsloth endpoint" in unlocks_col[unsloth_idx]


def test_keys_table_uses_template_install_links_for_compatible_profiles():
    cfg = Config(data={"llm.provider": "openai"})
    cfg.upsert_openai_profile(
        profile_id="ds4_local",
        label="DS4 Local",
        backend="ds4",
        base_url="http://localhost:8000/v1",
        api_key=None,
    )
    cfg.upsert_openai_profile(
        profile_id="llama_cpp_local",
        label="llama.cpp Local",
        backend="llama_cpp",
        base_url="http://localhost:8080/v1",
        api_key=None,
    )
    cfg.upsert_openai_profile(
        profile_id="custom_other",
        label="Custom Other",
        backend="other",
        base_url="http://localhost:9999/v1",
        api_key=None,
    )

    table = cfg.keys_table()
    service_col = list(getattr(table.columns[0], "_cells", []))
    signup_col = list(getattr(table.columns[5], "_cells", []))

    ds4_idx = service_col.index("OpenAI-compatible: DS4 Local")
    llama_idx = service_col.index("OpenAI-compatible: llama.cpp Local")
    custom_idx = service_col.index("OpenAI-compatible: Custom Other")

    assert "github.com/antirez/ds4" in signup_col[ds4_idx]
    assert "github.com/ggml-org/llama.cpp" in signup_col[llama_idx]
    assert signup_col[custom_idx] == "—"


def test_set_openai_key_rejects_invalid_format():
    cfg = Config(data={})
    with pytest.raises(ValueError, match="Invalid OpenAI API key format"):
        cfg.set("llm.openai_api_key", "not-a-key")


def test_save_merges_only_dirty_keys_and_preserves_existing_secrets(monkeypatch, tmp_path):
    config_path = tmp_path / "config.json"
    backup_path = tmp_path / "config.json.bak"
    config_path.write_text(
        json.dumps(
            {
                "llm.provider": "anthropic",
                "llm.openai_api_key": "sk-proj-AbCdEf1234567890xyz",
                "api.fastfold_cloud_key": "sk-ff-1234567890",
            }
        )
    )
    monkeypatch.setattr(config_mod, "CONFIG_FILE", config_path)
    monkeypatch.setattr(config_mod, "CONFIG_BACKUP_FILE", backup_path)

    cfg = Config.load()
    cfg.set("llm.provider", "openai")
    cfg.save()

    saved = json.loads(config_path.read_text())
    assert saved["llm.provider"] == "openai"
    assert saved["llm.openai_api_key"] == "sk-proj-AbCdEf1234567890xyz"
    assert saved["api.fastfold_cloud_key"] == "sk-ff-1234567890"
    assert backup_path.exists()


def test_load_reads_boltz_api_key_from_env(monkeypatch, tmp_path):
    config_path = tmp_path / "config.json"
    backup_path = tmp_path / "config.json.bak"
    monkeypatch.setattr(config_mod, "CONFIG_FILE", config_path)
    monkeypatch.setattr(config_mod, "CONFIG_BACKUP_FILE", backup_path)
    monkeypatch.setenv("BOLTZ_API_KEY", "sk_bc_env_key")

    cfg = Config.load()
    assert cfg.get("api.boltz_api_key") == "sk_bc_env_key"


def test_set_openai_key_accepts_project_format():
    cfg = Config(data={})
    key = "sk-proj-AbCdEf1234567890xyz"
    cfg.set("llm.openai_api_key", key)
    assert cfg.get("llm.openai_api_key") == key


def test_set_openai_key_accepts_non_sk_for_custom_compatible_endpoint():
    cfg = Config(
        data={
            "llm.openai_base_url": "http://ai-server.tail9762ec.ts.net:11434/v1",
        }
    )
    cfg.set("llm.openai_compatible_api_key", "ollama")
    assert cfg.get("llm.openai_compatible_api_key") == "ollama"


def test_llm_api_key_prefers_compatible_key_for_custom_endpoint():
    cfg = Config(
        data={
            "llm.provider": "openai",
            "llm.openai_base_url": "http://localhost:11434/v1",
            "llm.openai_api_key": "sk-proj-cloud-key",
            "llm.openai_compatible_api_key": "ollama",
        }
    )
    assert cfg.llm_api_key("openai") == "ollama"


def test_load_bootstraps_compatible_profile_when_legacy_key_exists_without_endpoint(monkeypatch, tmp_path):
    config_path = tmp_path / "config.json"
    backup_path = tmp_path / "config.json.bak"
    config_path.write_text(
        json.dumps(
            {
                "llm.provider": "anthropic",
                "llm.model": "omlx-model",
                "llm.openai_compatible_api_key": "fresh-key",
                "llm.openai_active_profile": "openai_cloud",
            }
        )
    )
    monkeypatch.setattr(config_mod, "CONFIG_FILE", config_path)
    monkeypatch.setattr(config_mod, "CONFIG_BACKUP_FILE", backup_path)

    cfg = Config.load()
    compatible_profiles = cfg.openai_profiles(include_cloud=False)
    assert compatible_profiles
    active_profile = cfg.get_openai_profile()
    assert active_profile is not None
    assert active_profile["backend"] == "omlx"
    assert active_profile["default_model"] == "omlx-model"
    assert cfg.get("llm.provider") == "openai"
    assert cfg.llm_openai_base_url() == "http://localhost:8000/v1"


def test_heals_openai_cloud_model_when_active_profile_is_local_backend():
    cfg = Config(
        data={
            "llm.provider": "openai",
            "llm.model": "gpt-5-nano",
            "llm.openai_profiles": {
                "openai_cloud": {
                    "label": "OpenAI Cloud",
                    "backend": "openai",
                    "base_url": "https://api.openai.com/v1",
                    "default_model": "gpt-5.5",
                },
                "ollama_local": {
                    "label": "Ollama Local",
                    "backend": "ollama",
                    "base_url": "http://localhost:11434/v1",
                    "default_model": "qwen3.6:32b",
                },
            },
            "llm.openai_active_profile": "ollama_local",
        }
    )

    assert cfg.get("llm.model") == "qwen3.6:32b"
    assert cfg.llm_openai_base_url() == "http://localhost:11434/v1"


def test_does_not_heal_openai_cloud_model_for_other_compatible_backend():
    cfg = Config(
        data={
            "llm.provider": "openai",
            "llm.model": "gpt-5-nano",
            "llm.openai_profiles": {
                "openai_cloud": {
                    "label": "OpenAI Cloud",
                    "backend": "openai",
                    "base_url": "https://api.openai.com/v1",
                    "default_model": "gpt-5.5",
                },
                "gateway_proxy": {
                    "label": "Gateway Proxy",
                    "backend": "other",
                    "base_url": "https://my-gateway.example/v1",
                    "default_model": "gpt-5-nano",
                },
            },
            "llm.openai_active_profile": "gateway_proxy",
        }
    )

    assert cfg.get("llm.model") == "gpt-5-nano"


def test_upsert_profile_key_does_not_get_overwritten_by_stale_legacy_projection():
    cfg = Config(
        data={
            "llm.provider": "openai",
            "llm.openai_profiles": {
                "openai_cloud": {
                    "label": "OpenAI Cloud",
                    "backend": "openai",
                    "base_url": "https://api.openai.com/v1",
                    "api_key": None,
                    "default_model": "gpt-5.5",
                },
                "omlx_local": {
                    "label": "oMLX Local",
                    "backend": "omlx",
                    "base_url": "http://127.0.0.1:8005/v1",
                    "api_key": "sk-omlx-old",
                    "default_model": "omlx-model",
                },
                "unsloth_local": {
                    "label": "Unsloth Local",
                    "backend": "unsloth",
                    "base_url": "http://localhost:8888/v1",
                    "api_key": "sk-omlx-wrong",
                    "default_model": "unsloth-model",
                },
            },
            "llm.openai_active_profile": "unsloth_local",
            "llm.openai_base_url": "http://localhost:8888/v1",
            "llm.openai_compatible_backend": "unsloth",
            "llm.openai_compatible_api_key": "sk-omlx-wrong",
        }
    )

    cfg.upsert_openai_profile(
        profile_id="unsloth_local",
        api_key="sk-unsloth-new",
        set_active=True,
    )

    unsloth_profile = cfg.get_openai_profile("unsloth_local")
    assert unsloth_profile is not None
    assert unsloth_profile["api_key"] == "sk-unsloth-new"
    assert cfg.get("llm.openai_compatible_api_key") == "sk-unsloth-new"


def test_set_legacy_compatible_key_updates_active_profile_key():
    cfg = Config(
        data={
            "llm.provider": "openai",
            "llm.openai_profiles": {
                "openai_cloud": {
                    "label": "OpenAI Cloud",
                    "backend": "openai",
                    "base_url": "https://api.openai.com/v1",
                    "api_key": None,
                    "default_model": "gpt-5.5",
                },
                "unsloth_local": {
                    "label": "Unsloth Local",
                    "backend": "unsloth",
                    "base_url": "http://localhost:8888/v1",
                    "api_key": "sk-unsloth-old",
                    "default_model": "unsloth-model",
                },
            },
            "llm.openai_active_profile": "unsloth_local",
            "llm.openai_base_url": "http://localhost:8888/v1",
            "llm.openai_compatible_backend": "unsloth",
            "llm.openai_compatible_api_key": "sk-unsloth-old",
        }
    )

    cfg.set("llm.openai_compatible_api_key", "sk-unsloth-fresh")
    profile = cfg.get_openai_profile("unsloth_local")
    assert profile is not None
    assert profile["api_key"] == "sk-unsloth-fresh"


def test_set_anthropic_key_rejects_invalid_format():
    cfg = Config(data={})
    with pytest.raises(ValueError, match="Invalid Anthropic API key format"):
        cfg.set("llm.anthropic_api_key", "sk-proj-not-anthropic")


def test_set_llm_key_blank_unsets_value():
    cfg = Config(data={"llm.openai_api_key": "sk-proj-AbCdEf1234567890xyz"})
    cfg.set("llm.openai_api_key", "   ")
    assert cfg.get("llm.openai_api_key") is None


def test_install_uv_flavor_roundtrip():
    cfg = Config(data={})
    cfg.set("install.uv_flavor", "all")
    assert cfg.get("install.uv_flavor") == "all"


def test_llm_preflight_rejects_unknown_provider():
    cfg = Config(data={"llm.provider": "mystery_provider"})
    issue = cfg.llm_preflight_issue()
    assert issue is not None
    assert "Unsupported llm.provider" in issue


def test_claude_code_tool_disabled_by_default():
    cfg = Config(data={})
    assert cfg.get("agent.enable_claude_code_tool") is False


def test_memory_retrieval_enabled_by_default():
    cfg = Config(data={})
    assert cfg.get("agent.memory_retrieval_enabled") is True


def test_quality_gate_defaults():
    cfg = Config(data={})
    assert cfg.get("agent.quality_gate_enabled") is True
    assert cfg.get("agent.quality_gate_strict") is False


def test_agent_profile_enterprise_applies_preset():
    cfg = Config(data={})
    cfg.set("agent.profile", "enterprise")
    assert cfg.get("agent.profile") == "enterprise"
    assert cfg.get("agent.quality_gate_strict") is True
    assert cfg.get("agent.allow_creative_hypotheses") is False
    assert cfg.get("agent.enable_claude_code_tool") is False
    assert cfg.get("enterprise.enforce_policy") is True


def test_agent_profile_research_applies_preset():
    cfg = Config(data={})
    cfg.set("agent.profile", "research")
    assert cfg.get("agent.profile") == "research"
    assert cfg.get("agent.quality_gate_strict") is False
    assert cfg.get("agent.allow_creative_hypotheses") is True
    assert cfg.get("enterprise.enforce_policy") is False


def test_agent_profile_pharma_applies_preset():
    cfg = Config(data={})
    cfg.set("agent.profile", "pharma")
    assert cfg.get("agent.profile") == "pharma"
    assert cfg.get("agent.quality_gate_strict") is True
    assert cfg.get("agent.allow_creative_hypotheses") is False
    assert cfg.get("agent.synthesis_style") == "pharma"
    assert cfg.get("agent.quality_gate_min_next_steps") == 3
    assert cfg.get("agent.quality_gate_max_next_steps") == 3
    assert cfg.get("enterprise.enforce_policy") is False


def test_agent_profile_invalid_raises():
    cfg = Config(data={})
    with pytest.raises(ValueError):
        cfg.set("agent.profile", "unknown-profile")


def test_default_output_dir_is_cwd_outputs_when_missing(tmp_path, monkeypatch):
    cfg_path = tmp_path / "missing_config.json"
    monkeypatch.setattr(config_mod, "CONFIG_FILE", cfg_path)
    cfg = Config.load()
    assert cfg.get("sandbox.output_dir") == config_mod.DEFAULTS["sandbox.output_dir"]


def test_load_migrates_legacy_home_output_dir(tmp_path, monkeypatch):
    legacy = str(Path.home() / ".ct" / "outputs")
    cfg_path = tmp_path / "config.json"
    cfg_path.write_text(json.dumps({"sandbox.output_dir": legacy}), encoding="utf-8")
    monkeypatch.setattr(config_mod, "CONFIG_FILE", cfg_path)

    with patch("agent.config.Path.cwd", return_value=tmp_path):
        cfg = Config.load()

    assert cfg.get("sandbox.output_dir") == str(tmp_path / "outputs")


# ── Config Schema Validation ──────────────────────────────────────────


class TestValidateConfig:
    """Tests for _validate_config()."""

    def test_valid_config_returns_empty(self):
        issues = _validate_config({})
        assert issues == []

    def test_unknown_key_warns(self):
        issues = _validate_config({"agent.typo_key": True})
        assert any("Unknown config key" in i and "typo_key" in i for i in issues)

    def test_type_error_bool_as_string(self):
        issues = _validate_config({"output.verbose": "yes"})
        assert any("Type error" in i and "output.verbose" in i for i in issues)

    def test_type_error_int_as_string(self):
        issues = _validate_config({"agent.max_iterations": "three"})
        assert any("Type error" in i and "agent.max_iterations" in i for i in issues)

    def test_type_error_float_as_string(self):
        issues = _validate_config({"llm.temperature": "hot"})
        assert any("Type error" in i and "llm.temperature" in i for i in issues)

    def test_correct_types_no_warnings(self):
        issues = _validate_config({
            "agent.max_iterations": 5,
            "output.verbose": False,
            "llm.temperature": 0.3,
            "llm.provider": "anthropic",
        })
        assert issues == []

    def test_range_max_iterations_zero(self):
        issues = _validate_config({"agent.max_iterations": 0})
        assert any("Range error" in i and "max_iterations" in i for i in issues)

    def test_range_max_iterations_negative(self):
        issues = _validate_config({"agent.max_iterations": -1})
        assert any("Range error" in i for i in issues)

    def test_range_synthesis_max_tokens_too_low(self):
        issues = _validate_config({"agent.synthesis_max_tokens": 100})
        assert any("Range error" in i and "synthesis_max_tokens" in i for i in issues)

    def test_range_synthesis_max_tokens_valid(self):
        issues = _validate_config({"agent.synthesis_max_tokens": 512})
        assert not any("synthesis_max_tokens" in i for i in issues)

    def test_range_sandbox_timeout_zero(self):
        issues = _validate_config({"sandbox.timeout": 0})
        assert any("Range error" in i and "sandbox.timeout" in i for i in issues)

    def test_interdependency_pharma_strict_false(self):
        issues = _validate_config({
            "agent.profile": "pharma",
            "agent.quality_gate_strict": False,
        })
        assert any("Interdependency warning" in i and "pharma" in i for i in issues)

    def test_interdependency_pharma_strict_true(self):
        issues = _validate_config({
            "agent.profile": "pharma",
            "agent.quality_gate_strict": True,
        })
        assert not any("Interdependency" in i for i in issues)

    def test_interdependency_research_strict_false_no_warning(self):
        issues = _validate_config({
            "agent.profile": "research",
            "agent.quality_gate_strict": False,
        })
        assert not any("Interdependency" in i for i in issues)

    def test_none_values_skipped(self):
        """None values should not trigger type errors."""
        issues = _validate_config({"llm.api_key": None})
        assert not any("Type error" in i and "llm.api_key" in i for i in issues)

    def test_validate_method_on_config_instance(self):
        cfg = Config(data={"agent.max_iterations": -1, "bogus_key": True})
        issues = cfg.validate()
        assert any("Range error" in i for i in issues)
        assert any("Unknown config key" in i for i in issues)

    def test_load_logs_validation_warnings(self, tmp_path, monkeypatch):
        """Config.load() should run validation and log warnings."""
        cfg_path = tmp_path / "config.json"
        cfg_path.write_text(json.dumps({"agent.max_iterations": -1}))
        monkeypatch.setattr(config_mod, "CONFIG_FILE", cfg_path)
        with patch("agent.config.logger") as mock_logger:
            Config.load()
            # Should have logged at least one warning about negative max_iterations
            assert mock_logger.warning.called
            calls = [str(c) for c in mock_logger.warning.call_args_list]
            assert any("max_iterations" in c for c in calls)
