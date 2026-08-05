"""Unit tests for /models modal helpers (sections, favorites, filter)."""

from __future__ import annotations

from ui.terminal.models_modal import (
    build_model_rows,
    first_selectable_index,
    run_models_modal,
)


def _opt(provider, model_id, display=None, profile_id=None, label=None):
    return {
        "provider": provider,
        "model_id": model_id,
        "display": display or model_id,
        "desc": "",
        "profile_id": profile_id,
        "provider_label": label or provider,
    }


def test_build_model_rows_favorites_and_recent_first():
    opts = [
        _opt("openai", "gpt-a", label="OpenAI"),
        _opt("anthropic", "claude-b", label="Anthropic"),
        _opt("openai", "gpt-c", label="OpenAI"),
    ]
    rows = build_model_rows(
        opts,
        favorite_keys=["anthropic:claude-b"],
        recent_keys=["openai:gpt-c", "openai:gpt-a"],
    )
    titles = [r.title for r in rows]
    assert titles[0] == "Favorites"
    assert "★" in titles[1] and "claude-b" in titles[1]
    assert "Recent" in titles
    # Favorited key should not also appear under Recent.
    recent_idx = titles.index("Recent")
    recent_block = titles[recent_idx + 1 :]
    next_headers = [t for t in recent_block if t in {"OpenAI", "Anthropic", "Favorites"}]
    recent_models = recent_block[: recent_block.index(next_headers[0])] if next_headers else recent_block
    assert all("claude-b" not in t for t in recent_models)


def test_build_model_rows_search_filters():
    opts = [
        _opt("openai", "gpt-a", display="GPT A", label="OpenAI"),
        _opt("anthropic", "claude-b", display="Claude B", label="Anthropic"),
    ]
    rows = build_model_rows(
        opts, favorite_keys=[], recent_keys=[], query="claude"
    )
    model_titles = [r.title for r in rows if r.kind == "model"]
    assert len(model_titles) == 1
    assert "Claude" in model_titles[0]


def test_first_selectable_skips_headers():
    opts = [_opt("openai", "m1", label="OpenAI")]
    rows = build_model_rows(opts, favorite_keys=[], recent_keys=[])
    assert rows[0].kind == "header"
    assert first_selectable_index(rows) == 1


def test_run_models_modal_skips_under_pytest():
    assert run_models_modal(object()) is False


def test_favorite_toggle_roundtrip():
    from agent.config import Config

    cfg = Config({"llm.favorite_models": []})
    assert cfg.toggle_model_favorite("gpt-x", "openai") is True
    assert cfg.is_model_favorite("gpt-x", "openai")
    assert cfg.toggle_model_favorite("gpt-x", "openai") is False
    assert not cfg.is_model_favorite("gpt-x", "openai")


def test_push_recent_model_dedupes_and_caps():
    from agent.config import Config

    cfg = Config({"llm.recent_models": []})
    for i in range(15):
        cfg.push_recent_model(f"m{i}", "openai")
    recent = cfg.recent_models()
    assert recent[0] == "openai:m14"
    assert len(recent) == 12
    cfg.push_recent_model("m10", "openai")
    assert cfg.recent_models()[0] == "openai:m10"
    assert cfg.recent_models().count("openai:m10") == 1


def test_format_context_window_label():
    from ui.terminal.models_modal import format_context_window_label

    assert format_context_window_label(1_000_000) == "1M"
    assert format_context_window_label(1_050_000) == "1.05M"
    assert format_context_window_label(200_000) == "200k"
    assert format_context_window_label(None) == ""


def test_build_model_rows_includes_context_and_effort():
    from agent.config import Config
    from ui.terminal.models_modal import build_model_rows

    opts = [_opt("openai", "gpt-5.6-sol", display="GPT-5.6 Sol", label="OpenAI")]
    cfg = Config(
        {
            "llm.reasoning_effort": "medium",
            "llm.reasoning_fast": False,
            "llm.model_reasoning": {},
        }
    )
    rows = build_model_rows(
        opts, favorite_keys=[], recent_keys=[], config=cfg
    )
    model_rows = [r for r in rows if r.kind == "model"]
    assert model_rows
    assert model_rows[0].context  # gpt-5.6 → ~1.05M
    assert "M" in model_rows[0].context
    assert model_rows[0].effort  # supports effort → Medium
