"""Unit tests for cli.py OpenAI-compatible setup helpers."""

import json
from unittest.mock import MagicMock, patch

import pytest
import typer

from agent.config import Config
from cli import (
    _fetch_compatible_models_for_setup,
    _infer_openai_compatible_backend,
    _is_openai_managed_base_url,
    _normalize_openai_base_url,
    _openai_models_url_from_base,
    _ollama_tags_url_from_base,
    _parse_provider_list,
    _prompt_boltz_api_key,
    _prompt_compatible_model_for_setup,
    _prompt_fastfold_cloud_api_key,
    _prompt_openai_compatible_backend,
    _prompt_openai_endpoint_mode,
    _prompt_setup_compatible_profile_id,
    _provider_label_for_source,
    _resolve_openai_base_url,
    _resolve_openai_compatible_endpoint,
    _resolve_provider_key,
    _setup_provider_runtime_id,
)


class TestOpenAIManagedBaseUrl:
    @pytest.mark.parametrize(
        "url,expected",
        [
            (None, True),
            ("", True),
            ("https://api.openai.com/v1", True),
            ("https://foo.openai.com/v1", True),
            ("http://localhost:11434/v1", False),
            ("https://gateway.example.com/v1", False),
        ],
    )
    def test_is_openai_managed(self, url, expected):
        assert _is_openai_managed_base_url(url) is expected

    def test_normalize_strips_trailing_slash(self):
        assert _normalize_openai_base_url("http://localhost:11434/v1/") == "http://localhost:11434/v1"
        assert _normalize_openai_base_url("   ") is None


class TestInferBackend:
    def test_ollama_from_port(self):
        assert _infer_openai_compatible_backend("http://localhost:11434/v1") == "ollama"

    def test_unsloth_from_key(self):
        assert _infer_openai_compatible_backend("http://localhost:8888/v1", "sk-unsloth-abc") == "unsloth"

    def test_lm_studio_from_port(self):
        assert _infer_openai_compatible_backend("http://localhost:1234/v1") == "lm_studio"

    def test_llama_cpp_from_port(self):
        assert _infer_openai_compatible_backend("http://localhost:8080/v1") == "llama_cpp"

    def test_ds4_from_endpoint_hint(self):
        assert _infer_openai_compatible_backend("http://localhost:8000/v1/ds4") == "ds4"

    def test_other_fallback(self):
        assert _infer_openai_compatible_backend("http://proxy.local/v1") == "other"


class TestUrlBuilders:
    def test_ollama_tags_url(self):
        assert _ollama_tags_url_from_base("http://localhost:11434/v1").endswith("/api/tags")

    def test_openai_models_url(self):
        assert _openai_models_url_from_base("http://localhost:8888").endswith("/v1/models")


class TestParseProviderList:
    def test_canonical_order(self, captured_console, monkeypatch):
        console, _ = captured_console
        monkeypatch.setattr("cli.console", console)
        assert _parse_provider_list("openai,anthropic") == ["anthropic", "openai"]

    def test_aliases(self, captured_console, monkeypatch):
        console, _ = captured_console
        monkeypatch.setattr("cli.console", console)
        assert _parse_provider_list("compatible") == ["openai_compatible"]

    def test_invalid_exits(self, captured_console, monkeypatch):
        console, _ = captured_console
        monkeypatch.setattr("cli.console", console)
        with pytest.raises(typer.Exit) as exc:
            _parse_provider_list("bogus")
        assert exc.value.exit_code == 2


class TestSetupProviderRuntimeId:
    def test_maps_compatible_to_openai(self):
        assert _setup_provider_runtime_id("openai_compatible") == "openai"
        assert _setup_provider_runtime_id("anthropic") == "anthropic"


class TestProviderLabelForSource:
    def test_github_owner_mapping(self):
        assert _provider_label_for_source("fastfold-ai/skills") == "Fastfold"
        assert _provider_label_for_source("anthropics/skills") == "Anthropic"

    def test_local_path(self, tmp_path):
        local = tmp_path / "my-skill"
        local.mkdir()
        assert _provider_label_for_source(str(local)) == "Local"

    def test_empty_is_custom(self):
        assert _provider_label_for_source("") == "Custom"


class TestPromptOpenAIHelpers:
    def test_prompt_endpoint_mode_non_tty_cloud(self, captured_console, monkeypatch):
        console, _ = captured_console
        monkeypatch.setattr("cli.console", console)
        monkeypatch.setattr("cli.sys.stdin.isatty", lambda: False)
        monkeypatch.setattr("cli.sys.stdout.isatty", lambda: False)
        monkeypatch.setattr("builtins.input", lambda _: "")
        assert _prompt_openai_endpoint_mode(default_mode="cloud") == "cloud"

    def test_prompt_endpoint_mode_compatible_alias(self, captured_console, monkeypatch):
        console, _ = captured_console
        monkeypatch.setattr("cli.console", console)
        monkeypatch.setattr("cli.sys.stdin.isatty", lambda: False)
        monkeypatch.setattr("cli.sys.stdout.isatty", lambda: False)
        monkeypatch.setattr("builtins.input", lambda _: "k")
        assert _prompt_openai_endpoint_mode() == "compatible"

    def test_prompt_compatible_backend_defaults(self, captured_console, monkeypatch):
        console, _ = captured_console
        monkeypatch.setattr("cli.console", console)
        monkeypatch.setattr("builtins.input", lambda _: "")
        assert _prompt_openai_compatible_backend(default_backend="unsloth") == "unsloth"

    def test_prompt_compatible_backend_numeric(self, captured_console, monkeypatch):
        console, _ = captured_console
        monkeypatch.setattr("cli.console", console)
        monkeypatch.setattr("builtins.input", lambda _: "2")
        assert _prompt_openai_compatible_backend() == "unsloth"

    def test_prompt_compatible_backend_numeric_lm_studio(self, captured_console, monkeypatch):
        console, _ = captured_console
        monkeypatch.setattr("cli.console", console)
        monkeypatch.setattr("builtins.input", lambda _: "6")
        assert _prompt_openai_compatible_backend() == "lm_studio"

    def test_prompt_compatible_backend_numeric_other_last(self, captured_console, monkeypatch):
        console, _ = captured_console
        monkeypatch.setattr("cli.console", console)
        monkeypatch.setattr("builtins.input", lambda _: "7")
        assert _prompt_openai_compatible_backend() == "other"


class TestResolveOpenAIEndpoints:
    def test_resolve_base_url_cli_managed_returns_none(self):
        cfg = Config(data={})
        assert _resolve_openai_base_url(cfg, cli_base_url="https://api.openai.com/v1") is None

    def test_resolve_base_url_cli_compatible(self):
        cfg = Config(data={})
        url = _resolve_openai_base_url(
            cfg,
            cli_base_url="http://localhost:11434/v1",
            force_mode="compatible",
        )
        assert url == "http://localhost:11434/v1"

    def test_resolve_compatible_endpoint_cli_unsloth(self, captured_console, monkeypatch):
        console, _ = captured_console
        monkeypatch.setattr("cli.console", console)
        cfg = Config(data={})
        url, backend = _resolve_openai_compatible_endpoint(
            cfg,
            cli_base_url="http://localhost:8888/v1",
            cli_backend="unsloth",
        )
        assert backend == "unsloth"
        assert url == "http://localhost:8888/v1"

    def test_resolve_compatible_endpoint_prompts(self, captured_console, monkeypatch):
        console, _ = captured_console
        monkeypatch.setattr("cli.console", console)
        cfg = Config(data={})
        monkeypatch.setattr("builtins.input", lambda _: "")
        url, backend = _resolve_openai_compatible_endpoint(cfg, cli_backend="ollama")
        assert backend == "ollama"
        assert url == "http://localhost:11434/v1"

    def test_resolve_compatible_endpoint_lm_studio_alias(self, captured_console, monkeypatch):
        console, _ = captured_console
        monkeypatch.setattr("cli.console", console)
        cfg = Config(data={})
        monkeypatch.setattr("builtins.input", lambda _: "")
        url, backend = _resolve_openai_compatible_endpoint(cfg, cli_backend="lmstudio")
        assert backend == "lm_studio"
        assert url == "http://localhost:1234/v1"


class TestFetchCompatibleModels:
    def test_unsloth_uses_openai_models(self, monkeypatch):
        monkeypatch.setattr(
            "cli._fetch_openai_models_for_setup",
            lambda base_url, api_key=None: ["model-a"],
        )
        assert _fetch_compatible_models_for_setup("http://x/v1", "unsloth") == ["model-a"]

    def test_lm_studio_uses_openai_models(self, monkeypatch):
        calls = []

        def fake_openai(*args, **kwargs):
            calls.append("openai")
            return ["local-model"]

        def fake_ollama(*args, **kwargs):
            calls.append("ollama")
            return ["should-not-be-used"]

        monkeypatch.setattr("cli._fetch_openai_models_for_setup", fake_openai)
        monkeypatch.setattr("cli._fetch_ollama_tags_for_setup", fake_ollama)
        names = _fetch_compatible_models_for_setup("http://localhost:1234/v1", "lm_studio")
        assert names == ["local-model"]
        assert calls == ["openai"]

    def test_ollama_falls_back_to_openai_models(self, monkeypatch):
        calls = []

        def fake_ollama(*args, **kwargs):
            calls.append("ollama")
            return []

        def fake_openai(*args, **kwargs):
            calls.append("openai")
            return ["gpt-oss:20b"]

        monkeypatch.setattr("cli._fetch_ollama_tags_for_setup", fake_ollama)
        monkeypatch.setattr("cli._fetch_openai_models_for_setup", fake_openai)
        names = _fetch_compatible_models_for_setup("http://localhost:11434/v1", "ollama")
        assert names == ["gpt-oss:20b"]
        assert calls == ["ollama", "openai"]


class TestPromptCompatibleModel:
    def test_manual_model_when_discovery_empty(self, captured_console, monkeypatch):
        console, buf = captured_console
        monkeypatch.setattr("cli.console", console)
        cfg = Config(data={"llm.model": "custom-model"})
        monkeypatch.setattr("cli._fetch_compatible_models_for_setup", lambda *a, **k: [])
        monkeypatch.setattr("builtins.input", lambda _: "")
        model = _prompt_compatible_model_for_setup(cfg, "http://localhost:11434/v1", "ollama")
        assert model == "custom-model"

    def test_select_discovered_model_by_number(self, captured_console, monkeypatch):
        console, _ = captured_console
        monkeypatch.setattr("cli.console", console)
        cfg = Config(data={})
        monkeypatch.setattr(
            "cli._fetch_compatible_models_for_setup",
            lambda *a, **k: ["alpha", "beta"],
        )
        monkeypatch.setattr("builtins.input", lambda _: "2")
        assert _prompt_compatible_model_for_setup(cfg, "http://x/v1", "ollama") == "beta"

    def test_retry_discovery_with_new_key_returns_override(self, captured_console, monkeypatch):
        console, _ = captured_console
        monkeypatch.setattr("cli.console", console)
        cfg = Config(data={"llm.model": "fallback-model"})
        calls = []

        def _fake_fetch(base_url, backend, api_key=None):
            calls.append(api_key)
            if len(calls) == 1:
                return []
            return ["omlx-model"]

        monkeypatch.setattr("cli._fetch_compatible_models_for_setup", _fake_fetch)
        monkeypatch.setattr("cli._prompt_openai_compatible_api_key", lambda backend="other": "sk-omlx-retry")
        answers = iter(["1", "1"])  # retry, then pick discovered model
        monkeypatch.setattr("builtins.input", lambda _: next(answers))

        result = _prompt_compatible_model_for_setup(cfg, "http://localhost:8000/v1", "omlx")
        assert result == ("omlx-model", "sk-omlx-retry")
        assert calls == [None, "sk-omlx-retry"]


class TestResolveProviderKey:
    def test_cli_key_anthropic_valid(self, captured_console, monkeypatch):
        console, _ = captured_console
        monkeypatch.setattr("cli.console", console)
        cfg = Config(data={})
        key = _resolve_provider_key(cfg, "anthropic", cli_key="sk-ant-api03-valid-key-here")
        assert key == "sk-ant-api03-valid-key-here"

    def test_cli_key_invalid_exits(self, captured_console, monkeypatch):
        console, _ = captured_console
        monkeypatch.setattr("cli.console", console)
        cfg = Config(data={})
        with pytest.raises(typer.Exit) as exc:
            _resolve_provider_key(cfg, "anthropic", cli_key="not-a-key")
        assert exc.value.exit_code == 2

    def test_openai_compatible_uses_default_ollama_key(self, captured_console, monkeypatch):
        console, _ = captured_console
        monkeypatch.setattr("cli.console", console)
        cfg = Config(data={})
        monkeypatch.setattr(
            "cli._prompt_openai_api_key_with_default",
            lambda default_key="ollama": "ollama",
        )
        key = _resolve_provider_key(
            cfg,
            "openai_compatible",
            openai_base_url="http://localhost:11434/v1",
            compatible_backend="ollama",
        )
        assert key == "ollama"

    def test_openai_compatible_lm_studio_uses_compatible_prompt(self, captured_console, monkeypatch):
        console, _ = captured_console
        monkeypatch.setattr("cli.console", console)
        cfg = Config(data={})
        monkeypatch.setattr("cli._prompt_openai_compatible_api_key", lambda backend="other": "lm-key")
        key = _resolve_provider_key(
            cfg,
            "openai_compatible",
            openai_base_url="http://localhost:1234/v1",
            compatible_backend="lm_studio",
        )
        assert key == "lm-key"


class TestCompatibleProfilePrompt:
    def test_prompt_setup_profile_non_tty_uses_active_compatible_profile(self, captured_console, monkeypatch):
        console, _ = captured_console
        monkeypatch.setattr("cli.console", console)
        monkeypatch.setattr("cli.sys.stdin.isatty", lambda: False)
        monkeypatch.setattr("cli.sys.stdout.isatty", lambda: False)

        cfg = Config(data={"llm.provider": "openai"})
        cfg.upsert_openai_profile(
            profile_id="unsloth_local",
            label="Unsloth Local",
            backend="unsloth",
            base_url="http://localhost:8888/v1",
            api_key="sk-unsloth",
            set_active=True,
        )
        assert _prompt_setup_compatible_profile_id(cfg) == "unsloth_local"

    def test_prompt_setup_profile_tty_invalid_selection_falls_back_to_new(self, captured_console, monkeypatch):
        console, _ = captured_console
        monkeypatch.setattr("cli.console", console)
        monkeypatch.setattr("cli.sys.stdin.isatty", lambda: True)
        monkeypatch.setattr("cli.sys.stdout.isatty", lambda: True)
        monkeypatch.setattr("builtins.input", lambda _: "bogus")

        cfg = Config(data={"llm.provider": "openai"})
        cfg.upsert_openai_profile(
            profile_id="omlx_local",
            label="oMLX Local",
            backend="omlx",
            base_url="http://localhost:8000/v1",
            api_key="sk-omlx",
            set_active=True,
        )
        assert _prompt_setup_compatible_profile_id(cfg) is None


class TestPromptFastfoldCloudApiKey:
    def test_keeps_existing_key(self, captured_console, monkeypatch):
        console, _ = captured_console
        monkeypatch.setattr("cli.console", console)
        cfg = Config(data={"api.fastfold_cloud_key": "sk-fastfold-123456"})
        monkeypatch.setattr("builtins.input", lambda _: "y")
        assert _prompt_fastfold_cloud_api_key(cfg, None) == "sk-fastfold-123456"

    def test_skip_and_interrupt_paths(self, captured_console, monkeypatch):
        console, _ = captured_console
        monkeypatch.setattr("cli.console", console)
        monkeypatch.delenv("BOLTZ_API_KEY", raising=False)
        cfg = Config(data={})

        monkeypatch.setattr("cli._prompt_masked_secret", lambda _message: "")
        assert _prompt_fastfold_cloud_api_key(cfg, None) is None

        monkeypatch.setattr(
            "cli._prompt_masked_secret",
            lambda _message: (_ for _ in ()).throw(KeyboardInterrupt()),
        )
        with pytest.raises(typer.Exit):
            _prompt_fastfold_cloud_api_key(cfg, None)


class TestPromptBoltzApiKey:
    def test_keeps_existing_key(self, captured_console, monkeypatch):
        console, _ = captured_console
        monkeypatch.setattr("cli.console", console)
        cfg = Config(data={"api.boltz_api_key": "sk_bc_existing_123456"})
        monkeypatch.setattr("builtins.input", lambda _: "y")
        assert _prompt_boltz_api_key(cfg, None) == "sk_bc_existing_123456"

    def test_skip_and_interrupt_paths(self, captured_console, monkeypatch):
        console, _ = captured_console
        monkeypatch.setattr("cli.console", console)
        monkeypatch.delenv("BOLTZ_API_KEY", raising=False)
        cfg = Config(data={})

        monkeypatch.setattr("cli._prompt_masked_secret", lambda _message: "")
        assert _prompt_boltz_api_key(cfg, None) is None

        monkeypatch.setattr(
            "cli._prompt_masked_secret",
            lambda _message: (_ for _ in ()).throw(KeyboardInterrupt()),
        )
        with pytest.raises(typer.Exit):
            _prompt_boltz_api_key(cfg, None)
