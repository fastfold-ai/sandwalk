"""Unit tests for mcp: chip mention steering context."""

from __future__ import annotations

from agent.mcp_manage.mentions import (
    build_mcp_mention_context,
    extract_mcp_mentions,
)


def test_extract_mcp_mentions_cli_space_and_web_forms():
    text = "please use mcp: raymol and also mcp:Linear thanks"
    assert extract_mcp_mentions(text) == ["raymol", "Linear"]


def test_extract_mcp_mentions_chip_token():
    text = "drive ⟦mcp:raymol:RayMol⟧ for 1UBQ"
    assert extract_mcp_mentions(text) == ["raymol"]


def test_extract_mcp_mentions_dedupes():
    text = "mcp: raymol mcp:raymol mcp: RayMol"
    assert extract_mcp_mentions(text) == ["raymol"]


def test_build_mcp_mention_context_lists_tools(monkeypatch):
    monkeypatch.setattr(
        "agent_server.store.AgentStore.list_mcp_servers",
        lambda self: [],
    )
    servers = [
        {
            "id": "srv-1",
            "catalog_id": "raymol",
            "name": "RayMol",
            "description": "Drive RayMol viewport",
            "enabled": True,
            "transport": "stdio",
        }
    ]
    tools = {
        "raymol": ["run_pymol_command", "capture_viewport", "search_pdb"],
        "RayMol": ["run_pymol_command", "capture_viewport", "search_pdb"],
    }
    ctx = build_mcp_mention_context(
        "open 1CRN with mcp: raymol",
        mcp_servers=servers,
        mcp_tools_by_server=tools,
    )
    assert "hard preference" in ctx
    assert "RayMol" in ctx
    assert "`run_pymol_command`" in ctx
    assert "`capture_viewport`" in ctx
    assert "Hugging Face" in ctx


def test_build_mcp_mention_context_disabled_warns(monkeypatch):
    monkeypatch.setattr(
        "agent_server.store.AgentStore.list_mcp_servers",
        lambda self: [
            {
                "id": "srv-1",
                "catalog_id": "raymol",
                "name": "RayMol",
                "enabled": False,
            }
        ],
    )
    ctx = build_mcp_mention_context(
        "mcp: raymol please",
        mcp_servers=[],
        mcp_tools_by_server={},
    )
    assert "not enabled" in ctx
    assert "RayMol" in ctx
    assert "do not improvise via web search" in ctx


def test_build_mcp_mention_context_empty_without_mentions():
    assert build_mcp_mention_context("hello there") == ""
