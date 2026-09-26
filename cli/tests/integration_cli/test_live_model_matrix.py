"""Live smoke: build_chat_model + one short invoke per curated provider.

Gated by ``RUN_LIVE_MODELS=1``. Skips providers that have no key configured.
Never prints secrets.
"""

from __future__ import annotations

import os

import pytest

_RUN = os.environ.get("RUN_LIVE_MODELS", "").strip().lower() in {"1", "true", "yes"}

# Cheap/latest defaults from the active picker — not the full 600-row catalog.
LIVE_TARGETS: list[tuple[str, str]] = [
    ("anthropic", "claude-sonnet-5"),
    ("anthropic", "claude-fable-5-1"),
    ("openai", "gpt-6-astra"),
    ("openai", "gpt-5.6-sol"),
    ("openrouter", "anthropic/claude-sonnet-5"),
    ("openrouter", "anthropic/claude-fable-5.1"),
    ("openrouter", "openai/gpt-6-astra"),
    ("openrouter", "google/gemini-3.5-flash"),
    ("google", "gemini-3.5-flash"),
    ("xai", "grok-4.5"),
    ("moonshot", "kimi-k3"),
]


@pytest.mark.skipif(not _RUN, reason="Set RUN_LIVE_MODELS=1 to ping live providers")
@pytest.mark.parametrize("provider,model", LIVE_TARGETS, ids=lambda pair: f"{pair[0]}:{pair[1]}")
def test_live_model_selector_ping(provider: str, model: str, monkeypatch) -> None:
    from pathlib import Path

    from langchain_core.messages import HumanMessage

    import agent.config as config_mod
    from agent.config import Config, sync_process_env_from_config
    from agent.deepagents_runtime.chat_model import build_chat_model

    real_dir = Path.home() / ".sandwalk"
    monkeypatch.setattr(config_mod, "CONFIG_DIR", real_dir, raising=False)
    monkeypatch.setattr(config_mod, "CONFIG_FILE", real_dir / "config.json", raising=False)
    monkeypatch.setattr(
        config_mod, "CONFIG_BACKUP_FILE", real_dir / "config.json.bak", raising=False
    )

    cfg = Config.load()
    sync_process_env_from_config()
    key = cfg.llm_api_key(provider)
    if not key:
        pytest.skip(f"no {provider} API key configured")

    cfg.set("llm.provider", provider)
    cfg.set("llm.model", model)
    chat = build_chat_model(cfg)
    reply = chat.invoke([HumanMessage(content="Reply with the single word pong.")])
    text = str(getattr(reply, "content", "") or "").strip()
    assert text, f"{provider}:{model} returned an empty reply"
