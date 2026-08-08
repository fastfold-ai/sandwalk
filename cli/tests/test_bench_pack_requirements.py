"""Unit tests for pack skill/MCP readiness checks."""

from __future__ import annotations

from types import SimpleNamespace

from agent_server.bench_service.pack_requirements import (
    missing_pack_requirements,
    partition_cells_by_requirements,
    question_missing_requirements,
    required_skills_mcps,
    skip_warning_message,
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
    warning = skip_warning_message(miss_skills, miss_mcps)
    assert warning is not None
    assert "skipped" in warning.lower()
    assert "exa" in warning


def test_question_missing_requirements_and_partition(monkeypatch):
    from agent_server.bench_service import pack_requirements as mod

    monkeypatch.setattr(mod, "_enabled_skill_names", lambda: {"fold"})
    monkeypatch.setattr(mod, "_enabled_mcp_ids", lambda store: {"pymol"})

    ok_q = SimpleNamespace(skills=["fold"], mcps=["pymol"], id="ok")
    skip_q = SimpleNamespace(skills=["fold"], mcps=["raymol"], id="skip")
    miss_s, miss_m = question_missing_requirements(
        skip_q, ready_skills={"fold"}, ready_mcps={"pymol"}
    )
    assert miss_s == []
    assert miss_m == ["raymol"]

    cells = [
        SimpleNamespace(question_id="ok", question=ok_q),
        SimpleNamespace(question_id="skip", question=skip_q),
    ]
    runnable, skipped = partition_cells_by_requirements(cells, store=object())
    assert len(runnable) == 1
    assert runnable[0].question_id == "ok"
    assert len(skipped) == 1
    assert skipped[0]["missing_mcps"] == ["raymol"]
    assert "raymol" in skipped[0]["reason"]
