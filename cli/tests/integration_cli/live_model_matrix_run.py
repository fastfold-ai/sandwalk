"""Run the live model-selector smoke outside pytest isolation."""

from __future__ import annotations

from langchain_core.messages import HumanMessage

from agent.config import Config, sync_process_env_from_config
from agent.deepagents_runtime.chat_model import build_chat_model

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


def main() -> int:
    cfg_base = Config.load()
    sync_process_env_from_config()
    failed = 0
    skipped = 0
    passed = 0
    for provider, model in LIVE_TARGETS:
        label = f"{provider}:{model}"
        if not cfg_base.llm_api_key(provider):
            print(f"SKIP {label} (no key)")
            skipped += 1
            continue
        cfg = Config.load()
        cfg.set("llm.provider", provider)
        cfg.set("llm.model", model)
        try:
            chat = build_chat_model(cfg)
            reply = chat.invoke(
                [HumanMessage(content="Reply with the single word pong.")]
            )
            text = str(getattr(reply, "content", "") or "").strip()
            if not text:
                raise RuntimeError("empty reply")
            preview = text.replace("\n", " ")[:80]
            print(f"PASS {label} -> {preview}")
            passed += 1
        except Exception as exc:  # noqa: BLE001
            failed += 1
            detail = " ".join(str(exc).split())[:220]
            print(f"FAIL {label} -> {exc.__class__.__name__}: {detail}")
    print(f"\n{passed} passed, {failed} failed, {skipped} skipped")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
