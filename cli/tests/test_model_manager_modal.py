"""Unit tests for /model-manager modal helpers."""

from __future__ import annotations

from types import SimpleNamespace

from ui.terminal.model_manager_modal import (
    collect_profile_rows,
    first_selectable_index,
    run_model_manager_modal,
)


def test_collect_profile_rows_includes_actions():
    terminal = SimpleNamespace(session=SimpleNamespace(config=None))

    class _Cfg:
        def openai_profiles(self, include_cloud=False):
            return {
                "local_lm": {
                    "label": "LM Studio",
                    "backend": "lmstudio",
                    "base_url": "http://localhost:1234/v1",
                }
            }

        def get(self, key, default=None):
            if key == "llm.openai_active_profile":
                return "local_lm"
            return default

    # Patch Config.load path via session.config
    terminal.session.config = _Cfg()
    terminal._compatible_backend_display_name = lambda b: b

    rows = collect_profile_rows(terminal)
    assert any(r.kind == "profile" and r.profile_id == "local_lm" for r in rows)
    assert any(r.kind == "action" and r.action == "add" for r in rows)
    assert first_selectable_index(rows) >= 1


def test_collect_profile_rows_search():
    terminal = SimpleNamespace(session=SimpleNamespace(config=None))

    class _Cfg:
        def openai_profiles(self, include_cloud=False):
            return {
                "a": {"label": "Alpha", "backend": "other", "base_url": "http://a"},
                "b": {"label": "Beta", "backend": "other", "base_url": "http://b"},
            }

        def get(self, key, default=None):
            return default

    terminal.session.config = _Cfg()
    terminal._compatible_backend_display_name = lambda b: b
    rows = collect_profile_rows(terminal, query="alpha")
    profiles = [r for r in rows if r.kind == "profile"]
    assert len(profiles) == 1
    assert profiles[0].title == "Alpha"


def test_run_model_manager_modal_skips_under_pytest():
    assert run_model_manager_modal(object()) is False
