"""Unit tests for pack skill/MCP readiness checks."""

from __future__ import annotations

from types import SimpleNamespace

from agent_server.bench_service.pack_requirements import (
    missing_pack_requirements,
    required_skills_mcps,
)


def test_required_skills_mcps_from_coverage():
    pack = SimpleNamespace(
        raw={
            "coverage": {
                "skills": ["fold", "boltz"],
                "mcps": ["pymol", "exa"],
            }
        },
        questions=[],
    )
    skills, mcps = required_skills_mcps(pack)
    assert skills == ["fold", "boltz"]
    assert mcps == ["pymol", "exa"]


def test_required_skills_mcps_falls_back_to_questions():
    pack = SimpleNamespace(
        raw={},
        questions=[
            SimpleNamespace(skills=["fold"], mcps=["pymol"]),
            SimpleNamespace(skills=["fold", "boltz"], mcps=["exa"]),
        ],
    )
    skills, mcps = required_skills_mcps(pack)
    assert skills == ["boltz", "fold"]
    assert mcps == ["exa", "pymol"]


def test_missing_pack_requirements(monkeypatch):
    from agent_server.bench_service import pack_requirements as mod

    pack = SimpleNamespace(
        raw={"coverage": {"skills": ["fold", "missing-skill"], "mcps": ["pymol", "exa"]}},
        questions=[],
    )
    monkeypatch.setattr(mod, "_enabled_skill_names", lambda: {"fold"})
    monkeypatch.setattr(mod, "_enabled_mcp_ids", lambda store: {"pymol"})
    miss_skills, miss_mcps = missing_pack_requirements(pack, store=object())
    assert miss_skills == ["missing-skill"]
    assert miss_mcps == ["exa"]
