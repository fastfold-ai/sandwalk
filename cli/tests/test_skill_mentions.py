"""Unit tests for slash/chip skill mention activation context."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from agent.skills.mentions import (
    build_skill_mention_context,
    extract_skill_mentions,
)


def test_extract_skill_mentions_slash_and_token():
    text = "please run /fold on 1UBQ and also ⟦/:boltz⟧ thanks"
    assert extract_skill_mentions(text) == ["fold", "boltz"]


def test_extract_skill_mentions_ignores_filesystem_paths():
    text = "read /Users/me/file and /tmp/out"
    assert extract_skill_mentions(text) == []


def test_build_skill_mention_context_preloads_and_hints(monkeypatch, tmp_path: Path):
    skill_dir = tmp_path / "fold"
    skill_dir.mkdir()
    skill_md = skill_dir / "SKILL.md"
    skill_md.write_text(
        "---\nname: fold\ndescription: Fold proteins\n---\n\n# fold\n\nUse create_job.py\n",
        encoding="utf-8",
    )
    info = SimpleNamespace(
        name="fold",
        enabled=True,
        path=skill_md,
        directory=skill_dir,
    )
    monkeypatch.setattr("agent.skills.skill_info", lambda name: info if name == "fold" else None)

    ctx = build_skill_mention_context(
        "use /fold with boltz-2",
        sandbox_backend="modal",
    )
    assert "User mentioned skill(s)" in ctx
    assert "read_file path: `/skills/fold/SKILL.md`" in ctx
    assert "host skill directory" in ctx
    assert str(skill_dir.resolve()) in ctx
    assert "### Preloaded SKILL.md: fold" in ctx
    assert "Use create_job.py" in ctx
    assert "not a filesystem directory" in ctx


def test_build_skill_mention_context_unknown_skill(monkeypatch):
    monkeypatch.setattr("agent.skills.skill_info", lambda _name: None)
    ctx = build_skill_mention_context("try /nope-skill-xyz")
    assert "not available" in ctx
    assert "/nope-skill-xyz" in ctx
    assert "skills.manage" in ctx


def test_build_skill_mention_context_empty_without_mentions():
    assert build_skill_mention_context("hello there") == ""
