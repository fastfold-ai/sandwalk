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
    assert rows[1].kind == "model"
    assert rows[1].favorite is True
    assert "★" not in rows[1].title
    assert "claude-b" in rows[1].title
    assert "Recent" in titles
    # Favorited key should not also appear under Recent.
    recent_idx = titles.index("Recent")
    recent_block = titles[recent_idx + 1 :]
    next_headers = [t for t in recent_block if t in {"OpenAI", "Anthropic", "Favorites"}]
    recent_models = recent_block[: recent_block.index(next_headers[0])] if next_headers else recent_block
    assert all("claude-b" not in t for t in recent_models)
    # Favorites/Recent are shortcuts — models still appear under providers.
    def _section_model_titles(header: str) -> list[str]:
        idx = titles.index(header)
        out: list[str] = []
        for row in rows[idx + 1 :]:
            if row.kind == "header":
                break
            if row.kind == "model":
                out.append(row.title)
        return out

    assert any("claude-b" in t for t in _section_model_titles("Anthropic"))
    openai_models = _section_model_titles("OpenAI")
    assert any("gpt-a" in t for t in openai_models)
    assert any("gpt-c" in t for t in openai_models)


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


def test_provider_display_label_unifies_openrouter():
    from ui.terminal.model_options import provider_display_label

    assert provider_display_label("openrouter") == "OpenRouter"
    assert provider_display_label("openrouter", fallback="OpenRouter") == "OpenRouter"
    assert provider_display_label("anthropic") == "Anthropic"


def test_build_model_rows_merges_openrouter_case_variants():
    from ui.terminal.models_modal import build_model_rows

    opts = [
        _opt("openrouter", "anthropic/claude-opus-5", display="Claude Opus 5", label="openrouter"),
        _opt(
            "openrouter",
            "inclusionai/ling-2.6-flash",
            display="Inclusionai/ling 2.6 Flash",
            label="OpenRouter",
        ),
    ]
    rows = build_model_rows(opts, favorite_keys=[], recent_keys=[])
    headers = [r.title for r in rows if r.kind == "header"]
    assert headers.count("OpenRouter") == 1
    assert "openrouter" not in headers


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


def test_collect_model_options_includes_hidden_deepseek():
    from agent.config import Config
    from ui.terminal.model_options import collect_model_options

    class _Term:
        session = type(
            "S",
            (),
            {
                "config": Config(
                    {
                        "llm.hidden_models": [
                            "deepseek:deepseek-v4-flash",
                            "deepseek:deepseek-v4-pro",
                        ],
                        "llm.openai_profiles": {},
                    }
                )
            },
        )()

    options, _warnings = collect_model_options(_Term())
    deepseek = [o for o in options if o.get("provider") == "deepseek"]
    assert deepseek
    assert all(o.get("enabled") is False for o in deepseek)
    providers = {o.get("provider") for o in options}
    assert "deepseek" in providers
    assert "minimax" in providers
    assert "mistral" in providers
    assert "qwen" in providers
    assert "together" in providers


def test_collect_model_options_local_fallback_when_discovery_empty(tmp_path, monkeypatch):
    from agent.config import Config
    from ui.terminal.model_options import collect_model_options

    cfg = Config(
        {
            "llm.hidden_models": [],
            "llm.openai_profiles": {
                "ollama_home": {
                    "label": "Ollama",
                    "backend": "ollama",
                    "base_url": "http://127.0.0.1:11434/v1",
                    "default_model": "llama3.2",
                }
            },
        }
    )

    class _Term:
        session = type("S", (), {"config": cfg})()

        def _fetch_compatible_models(self, *a, **k):
            return []

        def _compatible_backend_display_name(self, backend):
            return backend

        def _probe_compatible_profile(self, **k):
            return {"error": "connection refused"}

    options, warnings = collect_model_options(_Term())
    local = [o for o in options if o.get("provider") == "local"]
    assert local
    assert local[0]["model_id"] == "llama3.2"
    assert local[0]["provider_label"] == "Local"
    assert any("connection refused" in w for w in warnings)


def test_build_model_rows_marks_disabled():
    opts = [
        {
            **_opt("deepseek", "deepseek-v4-flash", display="DeepSeek V4 Flash", label="DeepSeek"),
            "enabled": False,
        }
    ]
    rows = build_model_rows(opts, favorite_keys=[], recent_keys=[])
    model_rows = [r for r in rows if r.kind == "model"]
    assert model_rows[0].enabled is False
    headers = [r.title for r in rows if r.kind == "header"]
    assert "DeepSeek" in headers


def test_favorite_row_keeps_provider_meta():
    opts = [
        _opt("moonshot", "kimi-k3", display="Kimi K3", label="Kimi"),
        _opt("openrouter", "moonshotai/kimi-k3", display="Kimi K3", label="OpenRouter"),
    ]
    rows = build_model_rows(
        opts,
        favorite_keys=["moonshot:kimi-k3", "openrouter:moonshotai/kimi-k3"],
        recent_keys=[],
    )
    # Only the Favorites section (provider sections also keep the same rows).
    fav_start = next(i for i, r in enumerate(rows) if r.title == "Favorites")
    favs = []
    for row in rows[fav_start + 1 :]:
        if row.kind == "header":
            break
        if row.kind == "model":
            favs.append(row)
    assert len(favs) == 2
    metas = {r.meta for r in favs}
    assert "Kimi" in metas
    assert "OpenRouter" in metas
