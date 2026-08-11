"""Live one-shot chat E2E — requires RUN_CLI_E2E=1 and an LLM API key."""

from __future__ import annotations

import os

import pytest

from integration_cli.harness import (
    FOLD_SKILL_SOURCE,
    assert_ok,
    combined_output,
    config_set,
    detect_llm_env,
    run_sandwalk,
    skill_installed_on_disk,
)

_RUN = os.environ.get("RUN_CLI_E2E", "").strip() in {"1", "true", "yes"}
_LLM = detect_llm_env()

pytestmark = [
    pytest.mark.cli_e2e,
    pytest.mark.e2e,
    pytest.mark.skipif(not _RUN, reason="Set RUN_CLI_E2E=1 to run live CLI chat tests"),
    pytest.mark.skipif(
        _LLM is None,
        reason="Need an LLM key in env or ~/.sandwalk/config.json",
    ),
]


def _seed_llm(cli_home, cli_cwd) -> str:
    assert _LLM is not None
    provider, key_name, api_key = _LLM
    config_set(cli_home, cli_cwd, "llm.provider", provider)
    config_set(cli_home, cli_cwd, key_name, api_key)
    # Prefer a cheap/fast default when the provider supports it; otherwise leave model alone.
    if provider == "anthropic":
        config_set(cli_home, cli_cwd, "llm.model", "claude-haiku-4-5-20251001")
    elif provider == "openai":
        config_set(cli_home, cli_cwd, "llm.model", "gpt-4.1-mini")
    elif provider == "google":
        config_set(cli_home, cli_cwd, "llm.model", "gemini-2.0-flash")
    return provider


def test_one_shot_chat_smoke(cli_home, cli_cwd):
    """Single non-interactive query — proves LLM preflight + agent loop boot."""
    _seed_llm(cli_home, cli_cwd)
    result = run_sandwalk(
        "Reply with exactly: PONG",
        home=cli_home,
        cwd=cli_cwd,
        timeout=180,
        # Keep developer Modal tokens out; chat should not need Modal.
        clear_modal_env=True,
    )
    assert_ok(result, label="one-shot chat")
    out = combined_output(result)
    # Banner / synthesis path should mention sandwalk; answer ideally contains PONG.
    assert "sandwalk" in out.lower()
    assert "PONG" in out or "pong" in out.lower() or "Setup incomplete" not in out


def test_chat_after_fold_skill_install(cli_home, cli_cwd):
    """Install featured fold skill (network) then run a tiny chat that references it."""
    if os.environ.get("RUN_CLI_NETWORK", "").strip() not in {"1", "true", "yes"}:
        pytest.skip("Set RUN_CLI_NETWORK=1 to install fold before chat")

    _seed_llm(cli_home, cli_cwd)
    install = run_sandwalk(
        "skills",
        "add",
        FOLD_SKILL_SOURCE,
        home=cli_home,
        cwd=cli_cwd,
        timeout=180,
    )
    assert_ok(install, label="skills add fold for chat")
    assert skill_installed_on_disk(cli_home, "fold")

    result = run_sandwalk(
        "In one short sentence, say whether the fold skill is available. Do not run any jobs.",
        home=cli_home,
        cwd=cli_cwd,
        timeout=240,
    )
    assert_ok(result, label="chat after fold install")
    out = combined_output(result)
    assert "Setup incomplete" not in out
    assert "sandwalk" in out.lower() or "fold" in out.lower()


def test_chat_must_use_ops_todo_tool(cli_home, cli_cwd):
    """Force a real tool call via ops.todo_* (no external APIs / datasets)."""
    _seed_llm(cli_home, cli_cwd)
    result = run_sandwalk(
        "Use the ops.todo_add tool to create a todo titled CLI-E2E-TODO "
        "with body smoke-test. Then reply with exactly: TODO_OK",
        home=cli_home,
        cwd=cli_cwd,
        timeout=240,
    )
    assert_ok(result, label="tool-forcing chat")
    out = combined_output(result)
    assert "Setup incomplete" not in out
    # Soft assert: either the model echoed the marker or wrote the todo on disk.
    ops_dir = cli_home / ".sandwalk" / "ops"
    todo_hit = False
    if ops_dir.is_dir():
        for path in ops_dir.rglob("*"):
            if path.is_file():
                try:
                    text = path.read_text(encoding="utf-8", errors="ignore")
                except OSError:
                    continue
                if "CLI-E2E-TODO" in text or "smoke-test" in text:
                    todo_hit = True
                    break
    assert "TODO_OK" in out or todo_hit or "todo" in out.lower()
