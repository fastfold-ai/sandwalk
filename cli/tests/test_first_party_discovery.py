"""OpenAI and Anthropic /v1/models feed the catalog with families we did not hardcode."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from agent.config import Config
from agent_server.models_service import first_party_discovery as fpd

OPENAI_PAYLOAD = {
    "data": [
        {"id": "gpt-7-nova", "object": "model"},          # brand-new family → enabled
        {"id": "gpt-6-astra", "object": "model"},         # curated → skipped
        {"id": "gpt-6-sol", "object": "model"},           # new GPT-6 → enabled
        {"id": "gpt-5.2", "object": "model"},             # older family → hidden
        {"id": "gpt-5.2-2025-12-11", "object": "model"},  # dated snapshot → dropped
        {"id": "gpt-5.1-chat-latest", "object": "model"}, # alias → dropped
        {"id": "gpt-realtime-2.1", "object": "model"},    # realtime → dropped
        {"id": "gpt-image-2.5", "object": "model"},       # image → dropped
        {"id": "text-embedding-3-large", "object": "model"},
        {"id": "o3", "object": "model"},
    ]
}

ANTHROPIC_PAGE_1 = {
    "data": [
        {
            "id": "claude-sonnet-6",
            "display_name": "Claude Sonnet 6",
            "line": "sonnet",
            "max_input_tokens": 2_000_000,
            "deprecated_at": None,
        },
        {
            "id": "claude-opus-4-7",
            "display_name": "Claude Opus 4.7",
            "line": "opus",
            "max_input_tokens": 1_000_000,
            "deprecated_at": "2026-12-01T00:00:00Z",
        },
        {"id": "claude-fable-5-1", "display_name": "Claude Fable 5.1", "line": "fable"},
    ],
    "has_more": True,
    "last_id": "claude-fable-5-1",
}
ANTHROPIC_PAGE_2 = {
    "data": [{"id": "claude-haiku-6", "display_name": "Claude Haiku 6", "line": "haiku"}],
    "has_more": False,
}


@pytest.fixture(autouse=True)
def _fresh_cache():
    fpd._reset_cache_for_tests()
    yield
    fpd._reset_cache_for_tests()


def test_openai_filter_keeps_chat_families_and_drops_snapshots():
    with patch.object(fpd, "_get_json", return_value=OPENAI_PAYLOAD):
        models = fpd.fetch_openai_models("sk-test")
    ids = [m.id for m in models]
    assert ids[0] == "gpt-7-nova"  # newest family first
    assert "gpt-6-sol" in ids and "gpt-5.2" in ids and "o3" in ids
    for dropped in ("gpt-5.2-2025-12-11", "gpt-5.1-chat-latest", "gpt-realtime-2.1", "gpt-image-2.5", "text-embedding-3-large"):
        assert dropped not in ids


def test_anthropic_fetch_follows_pagination_and_reads_metadata():
    pages = iter([ANTHROPIC_PAGE_1, ANTHROPIC_PAGE_2])
    with patch.object(fpd, "_get_json", side_effect=lambda *a, **k: next(pages)):
        models = fpd.fetch_anthropic_models("sk-ant-test")
    by_id = {m.id: m for m in models}
    assert set(by_id) == {"claude-sonnet-6", "claude-opus-4-7", "claude-fable-5-1", "claude-haiku-6"}
    assert by_id["claude-sonnet-6"].label == "Claude Sonnet 6"
    assert by_id["claude-sonnet-6"].context_window == 2_000_000
    assert by_id["claude-sonnet-6"].extra["line"] == "sonnet"
    assert by_id["claude-opus-4-7"].deprecated is True
    assert "deprecated" in by_id["claude-opus-4-7"].description


def test_discovered_items_skip_curated_and_set_defaults(tmp_path):
    cfg = Config.load()
    cfg.set("llm.openai_api_key", "sk-test")
    cfg.set("llm.anthropic_api_key", "sk-ant-test")

    def fake_get(url, headers, params=None):
        if "openai" in url:
            return OPENAI_PAYLOAD
        return ANTHROPIC_PAGE_2 if params and params.get("after_id") else {**ANTHROPIC_PAGE_1}

    # What the curated catalog already lists (newest Opus there is 5.5).
    known = {"gpt-6-astra", "claude-fable-5-1", "claude-opus-5-5"}
    hidden: set[str] = set()
    with patch.object(fpd, "_get_json", side_effect=fake_get), patch.object(Config, "save", lambda self: None):
        items = fpd.first_party_discovered_items(cfg, hidden, known, enabled_only=False)

    rows = {(i.provider, i.id): i for i in items}
    assert ("openai", "gpt-6-astra") not in rows          # curated row wins
    assert ("anthropic", "claude-fable-5-1") not in rows
    assert rows[("openai", "gpt-7-nova")].enabled is True
    assert rows[("openai", "gpt-6-sol")].enabled is True
    assert rows[("openai", "gpt-5.2")].enabled is False     # older family starts hidden
    assert rows[("anthropic", "claude-sonnet-6")].enabled is True
    assert rows[("anthropic", "claude-sonnet-6")].context_window == 2_000_000
    assert rows[("anthropic", "claude-opus-4-7")].enabled is False  # deprecated + older than Opus 5.5
    assert rows[("anthropic", "claude-haiku-6")].enabled is True   # no curated Haiku newer than it
    assert rows[("openai", "gpt-6-sol")].label == "GPT-6 Sol"
    assert rows[("openai", "o3")].label == "o3"
    # Everything discovered is now "known" so later providers do not duplicate it.
    assert {"gpt-7-nova", "gpt-6-sol", "claude-sonnet-6"} <= known


def test_fetch_failure_is_cached_briefly_and_keeps_static_catalog(tmp_path):
    cfg = Config.load()
    cfg.set("llm.openai_api_key", "sk-test")
    calls = {"n": 0}

    def boom(*_a, **_k):
        calls["n"] += 1
        raise RuntimeError("network down")

    with patch.object(fpd, "_get_json", side_effect=boom):
        first = fpd.first_party_discovered_items(cfg, set(), set(), enabled_only=False)
        second = fpd.first_party_discovered_items(cfg, set(), set(), enabled_only=False)
    assert first == [] and second == []
    assert calls["n"] == 1  # second call served from the error cache


def test_no_key_means_no_request():
    cfg = Config.load()
    for key in ("llm.openai_api_key", "llm.anthropic_api_key"):
        cfg.set(key, "")
    with patch.object(fpd, "_get_json", side_effect=AssertionError("should not fetch")):
        assert fpd.first_party_discovered_items(cfg, set(), set(), enabled_only=False) == []
