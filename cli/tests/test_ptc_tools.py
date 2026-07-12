"""Tests for Programmatic Tool Calling (PTC) support."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from agent.ptc_tools import (
    build_tool_catalog,
    build_tools_namespace,
    search_tools_text,
)


@pytest.fixture
def session():
    class _Cfg:
        def get(self, key, default=None):
            return default

    return SimpleNamespace(config=_Cfg())


class TestToolsNamespace:
    def test_categories_and_callables(self, session):
        ns = build_tools_namespace(session)
        assert isinstance(ns.categories, dict)
        assert ns.categories.get("chemistry", 0) > 0
        # nested namespace exposes the short name as a callable
        assert callable(ns.chemistry.descriptors)

    def test_list_helper_returns_dotted_names(self, session):
        ns = build_tools_namespace(session)
        names = ns.list("chemistry")
        assert all(n.startswith("chemistry.") for n in names)
        assert "chemistry.descriptors" in names

    def test_callable_runs_tool(self, session):
        ns = build_tools_namespace(session)
        res = ns.chemistry.descriptors(smiles="CCO")
        assert isinstance(res, dict)
        assert "summary" in res

    def test_exclude_categories_drops_namespace(self, session):
        ns = build_tools_namespace(session, exclude_categories={"chemistry"})
        assert not hasattr(ns, "chemistry")
        assert "chemistry" not in ns.categories


class TestSearchTools:
    def test_search_matches_admet(self):
        out = search_tools_text("admet predict", limit=5)
        assert "tools.safety.admet_predict(" in out

    def test_search_respects_category(self):
        out = search_tools_text("descriptors", category="chemistry", limit=5)
        assert "tools.chemistry." in out
        # no cross-category leakage
        for line in out.splitlines():
            if line.strip().startswith("- tools."):
                assert line.strip().startswith("- tools.chemistry.")

    def test_search_no_match_message(self):
        out = search_tools_text("zzz_nonexistent_capability_qqq", limit=5)
        assert "No domain tools matched" in out


class TestCatalog:
    def test_catalog_is_compact_and_lists_tools(self):
        cat = build_tool_catalog()
        # Compact: the names-only catalog should be far smaller than the full
        # per-tool schemas. Guard well under that ceiling.
        assert len(cat) < 12_000
        assert "Programmatic Tool Calling (PTC)" in cat
        assert "chemistry:" in cat

    def test_catalog_excludes_categories(self):
        cat = build_tool_catalog(exclude_categories={"chemistry"})
        assert "\n- chemistry:" not in cat
