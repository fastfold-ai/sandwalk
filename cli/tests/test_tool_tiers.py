"""Tests for core vs extra tool tiers and default hide migration."""

from __future__ import annotations

from agent.tool_tiers import (
    CORE_TOOL_NAMES,
    default_hidden_tool_ids,
    is_core_tool,
    tool_tier,
)


def test_core_tools_are_labeled_core():
    for name in CORE_TOOL_NAMES:
        assert tool_tier(name) == "core"
        assert is_core_tool(name)


def test_unknown_tools_are_extra():
    assert tool_tier("omics.something") == "extra"
    assert not is_core_tool("chemistry.descriptors")


def test_default_hidden_excludes_core():
    all_ids = list(CORE_TOOL_NAMES) + ["omics.foo", "chemistry.bar"]
    hidden = default_hidden_tool_ids(all_ids)
    assert "omics.foo" in hidden
    assert "chemistry.bar" in hidden
    for name in CORE_TOOL_NAMES:
        assert name not in hidden
