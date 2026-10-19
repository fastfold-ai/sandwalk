"""Coding-suite loaders and MCP mention chips without a live store."""

from __future__ import annotations

import json

from agent.mcp_manage import mentions
from agent_server.bench_service import coding_suites as coding


def test_coding_suite_load(tmp_path, monkeypatch):
    suite = coding.CODING_SUITES["mbpp"]
    sizes = coding.catalog_sample_sizes(suite)
    assert sizes[-1] == suite.full_size
    assert coding.count_fixture("missing") == 0
    assert coding.dataset_available("missing") is False
    monkeypatch.setattr(coding, "bench_cache_root", lambda: tmp_path)
    monkeypatch.setattr(coding, "bench_root", lambda: None)
    monkeypatch.setattr(coding, "fixtures_dir", lambda: None)
    assert coding.resolve_dataset_path(suite) is None
    try:
        coding.load_coding_items("mbpp")
        raise AssertionError("expected missing dataset")
    except FileNotFoundError:
        pass

    path = tmp_path / ".cache" / "mcq" / "mbpp.jsonl"
    path.parent.mkdir(parents=True)
    rows = [
        {"task_id": 1, "prompt": "add", "test_list": ["assert add(1, 1) == 2"]},
        {"task_id": 2, "text": "sub", "test_list": []},
        {"task_id": 3, "prompt": "mul", "test_list": ["assert mul(2, 2) == 4"], "test_setup_code": "import math"},
    ]
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n\n", encoding="utf-8")
    assert coding.dataset_available("mbpp") is True
    items = coding.load_coding_items("mbpp", sample_size=0)
    assert len(items) == 2
    sampled = coding.load_coding_items("mbpp", sample_size=1)
    assert len(sampled) == 1
    prompt = coding.format_coding_prompt("mbpp", items[0])
    assert "add" in prompt and "python" in prompt
    other = coding.format_coding_prompt("livecodebench", {"question": "read stdin"})
    assert "stdin" in other
    assert coding._normalize("livecodebench", {"question_id": "q", "public_test_cases": None}) is None


def test_mcp_mentions(monkeypatch):
    assert mentions._normalize_key("Ray Mol") == "ray-mol"
    assert mentions._mention_from_plain("mcp: raymol") == "raymol"
    assert mentions._mention_from_token("") == ""
    assert mentions._mention_from_token("pymol") == "pymol"
    assert mentions._mention_from_token(":Name") == "Name"
    text = "use ⟦mcp:pymol:PyMOL⟧ and mcp:raymol and mcp:raymol"
    found = mentions.extract_mcp_mentions(text)
    assert found[0] == "pymol"
    assert "raymol" in [item.lower() for item in found]
    assert mentions.extract_mcp_mentions("") == []
    server = {"catalog_id": "pymol", "id": "srv", "name": "PyMOL"}
    assert mentions._match_server("pymol", [server]) is server
    assert mentions._match_server("", [server]) is None
    assert mentions._match_catalog("pymol") is not None
    assert mentions._match_catalog("") is None
    names = mentions._tool_names_for(server, {"pymol": ["fetch"], "srv": ["other"]})
    assert names == ["fetch"]
    assert mentions._tool_names_for(server, None) == []
    assert mentions.build_mcp_mention_context("hello") == ""

    class _Store:
        def list_mcp_servers(self):
            return [{"catalog_id": "raymol", "name": "RayMol", "enabled": False}]

    monkeypatch.setattr("agent_server.store.AgentStore", _Store)
    ctx = mentions.build_mcp_mention_context(
        "please use mcp:pymol",
        mcp_servers=[{"catalog_id": "pymol", "name": "PyMOL", "enabled": True}],
        mcp_tools_by_server={"pymol": ["fetch_pdb"]},
    )
    assert "pymol" in ctx.lower() or "PyMOL" in ctx
