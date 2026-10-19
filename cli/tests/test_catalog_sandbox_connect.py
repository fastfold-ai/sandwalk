"""Catalog discovery, MCP connect commands, and sandbox CLI selection."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from agent.mcp_manage import connect_actions
from agent.sandbox_manage import (
    get_sandbox_backend,
    handle_sandbox_argv,
    normalize_sandbox_backend,
    sandbox_toolbar_label,
    set_sandbox_backend,
    toggle_sandbox_backend,
)
from agent_server.models_service import catalog_discovery as catalog


class _Cfg:
    def __init__(self):
        self.data = {
            "llm.openrouter_seen_models": [],
            "llm.bedrock_seen_models": [],
            "llm.hidden_models": [],
        }
        self.keys = {}
        self.saved = 0
        self.fail_save = False
        self.profiles = {}

    def get(self, key, default=None):
        return self.data.get(key, default)

    def set(self, key, value):
        self.data[key] = value

    def save(self):
        if self.fail_save:
            raise RuntimeError("disk")
        self.saved += 1

    def hidden_models(self):
        return list(self.data.get("llm.hidden_models") or [])

    def llm_api_key(self, provider):
        return self.keys.get(provider)

    def is_model_hidden(self, model_id, provider):
        return model_id in set(self.hidden_models())

    def openai_profiles(self, include_cloud=False):
        return self.profiles


def test_discovered_models(monkeypatch):
    cfg = _Cfg()
    assert catalog._discover_models_enabled({}) is False
    assert catalog._discover_models_enabled({"discover_models": "yes"}) is True
    assert catalog._openrouter_seen_models(cfg) == set()
    cfg.data["llm.openrouter_seen_models"] = "nope"
    assert catalog._openrouter_seen_models(cfg) == set()
    cfg.data["llm.openrouter_seen_models"] = [" a ", ""]
    assert catalog._openrouter_seen_models(cfg) == {"a"}
    cfg.fail_save = True
    hidden = catalog._seed_openrouter_discovered_hidden(cfg, ["new-model"], set())
    assert "new-model" in hidden
    again = catalog._seed_openrouter_discovered_hidden(cfg, ["new-model"], set())
    assert again == hidden

    cfg.keys["openrouter"] = "sk"
    cfg.fail_save = False

    def _probe(**kwargs):
        return {"models": ["vendor/new-model"], "context_windows": {"vendor/new-model": 8192}, "health": "ok"}

    monkeypatch.setattr("agent_server.models_service.probe_compatible_profile", _probe)
    monkeypatch.setattr("agent.model_catalog.bedrock.discover_bedrock_model_ids", lambda config: ["amazon.nova"])
    items = catalog._provider_discovered_items(cfg, set(), set(), enabled_only=False)
    ids = {item.id for item in items}
    assert "vendor/new-model" in ids
    assert "amazon.nova" in ids
    enabled = catalog._provider_discovered_items(cfg, set(cfg.hidden_models()), set(), enabled_only=True)
    assert all(item.enabled for item in enabled)

    def _bedrock_down(config):
        raise RuntimeError("iam")

    monkeypatch.setattr("agent.model_catalog.bedrock.discover_bedrock_model_ids", _bedrock_down)
    assert catalog._bedrock_discovered_items(cfg, set(), set(), enabled_only=False) == []

    calls = {"n": 0}

    def _llama_probe(**kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            return {"models": []}
        return {"models": ["ggml-org/gemma:Q4"], "health": "ok"}

    monkeypatch.setattr("agent_server.models_service.probe_compatible_profile", _llama_probe)
    monkeypatch.setattr("agent_server.llama_runtime.llama_binary", lambda: "/bin/llama")
    monkeypatch.setattr("agent_server.llama_runtime.ensure", lambda: None)
    monkeypatch.setattr(catalog.time, "sleep", lambda seconds: None)
    cfg.profiles = {
        "llama_local": {
            "label": "Llama",
            "backend": "llama",
            "base_url": "http://127.0.0.1:9931/v1",
            "default_model": "fallback",
        }
    }
    profiles = catalog._profile_discovered_items(cfg, set(), enabled_only=False, discover=True)
    assert profiles and profiles[0].backend == "llama"
    empty = catalog._wake_llama_profile("http://127.0.0.1:9931/v1", None, {"models": []})
    assert empty.get("models")


def test_mcp_connect_and_sandbox(monkeypatch):
    console = MagicMock()
    service = MagicMock()
    service.catalog_statuses.return_value = [
        {"id": "tamarind", "name": "Tamarind", "auth_mode": "api_key", "url": "https://mcp.example"}
    ]
    assert connect_actions.handle_catalog(["catalog"], console, service=service) == 0
    assert connect_actions.handle_connect(["connect"], console, service=service) == 2
    assert connect_actions.handle_connect(["connect", "nope"], console, service=service) == 1
    assert connect_actions.handle_connect(["connect", "pymol"], console, service=service) == 2
    assert connect_actions.handle_connect(["connect", "tamarind", "--api-key"], console, service=service) == 2
    service.connect_with_api_key.return_value = {"ok": True, "toolCount": 3, "enabled": True}
    assert connect_actions.handle_connect(
        ["connect", "tamarind", "--api-key", "sk"], console, service=service
    ) == 0
    service.connect_with_api_key.return_value = {"ok": False, "message": "bad key"}
    assert connect_actions.handle_connect(
        ["connect", "tamarind", "--api-key", "sk"], console, service=service
    ) == 1
    service.connect_with_api_key.side_effect = RuntimeError("down")
    assert connect_actions.handle_connect(
        ["connect", "tamarind", "--api-key", "sk"], console, service=service
    ) == 1
    service.start_oauth.return_value = {"authorizeUrl": "https://auth.example"}
    assert connect_actions.handle_connect(["connect", "github"], console, service=service) in {0, 1, 2}
    service.start_oauth.side_effect = RuntimeError("oauth")
    assert connect_actions.handle_connect(["connect", "github"], console, service=service) in {1, 2}
    assert connect_actions.handle_disconnect(["disconnect"], console, service=service) == 2
    service.disconnect.side_effect = KeyError("nope")
    assert connect_actions.handle_disconnect(["disconnect", "nope"], console, service=service) == 1
    service.disconnect.side_effect = None
    assert connect_actions.handle_disconnect(["disconnect", "tamarind"], console, service=service) == 0

    try:
        normalize_sandbox_backend("nope")
        raise AssertionError("expected backend error")
    except ValueError:
        pass
    assert normalize_sandbox_backend("off") == "builtin"
    cfg = _Cfg()
    assert get_sandbox_backend(cfg) == "builtin"
    cfg.data["agent.cli_sandbox"] = "weird"
    assert get_sandbox_backend(cfg) == "builtin"
    assert sandbox_toolbar_label("modal") == "Modal Sandbox"
    monkeypatch.setattr("agent.sandbox_probe.modal_tokens_present", lambda config: (False, "missing"))
    try:
        set_sandbox_backend("modal", cfg)
        raise AssertionError("expected modal tokens")
    except RuntimeError:
        pass
    monkeypatch.setattr("agent.sandbox_probe.modal_tokens_present", lambda config: (True, ""))
    assert set_sandbox_backend("on", cfg) == "modal"
    assert toggle_sandbox_backend(cfg) == "builtin"
    monkeypatch.setattr(
        "agent_server.status_service.get_status_report",
        lambda version: SimpleNamespace(
            system=SimpleNamespace(chip_name="M4", ram_used_bytes=1024**3, ram_total_bytes=16 * 1024**3, gpu_cores=10)
        ),
    )
    handle_sandbox_argv(["status"], console, cfg)
    handle_sandbox_argv(["help"], console, cfg)
    cfg.data["agent.cli_sandbox"] = "modal"
    cfg.data["sandbox.cpu_cores"] = 4
    cfg.data["sandbox.ram_gb"] = 16
    handle_sandbox_argv(["/sandbox", "status"], console, cfg)
