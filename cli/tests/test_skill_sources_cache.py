"""Skill staging roots are cached per name set and invalidated on mutation."""

from __future__ import annotations

import pytest

from agent.deepagents_runtime import skills_sources


@pytest.fixture(autouse=True)
def _clear_cache():
    skills_sources.invalidate_skill_sources_cache()
    yield
    skills_sources.invalidate_skill_sources_cache()


def test_second_call_skips_staging(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    staged = tmp_path / "stage"
    staged.mkdir()
    calls: list[list[str]] = []

    def fake_stage(names: list[str]) -> list[str]:
        calls.append(list(names))
        return [str(staged)]

    monkeypatch.setattr(skills_sources, "_stage_skill_source_dirs", fake_stage)
    assert skills_sources.skill_source_dirs_for_names(["b", "a"]) == [str(staged)]
    # Same set, different order / duplicates → cache hit.
    assert skills_sources.skill_source_dirs_for_names(["a", "b", "a"]) == [str(staged)]
    assert calls == [["b", "a"]]


def test_cache_invalidates_on_mutation_and_missing_dir(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    staged = tmp_path / "stage"
    staged.mkdir()
    calls = 0

    def fake_stage(names: list[str]) -> list[str]:
        nonlocal calls
        calls += 1
        return [str(staged)]

    monkeypatch.setattr(skills_sources, "_stage_skill_source_dirs", fake_stage)
    skills_sources.skill_source_dirs_for_names(["a"])
    skills_sources.invalidate_skill_sources_cache()
    skills_sources.skill_source_dirs_for_names(["a"])
    assert calls == 2
    # Staging dir vanished (tmp cleaner) → re-stage instead of returning a dead path.
    staged.rmdir()
    skills_sources.skill_source_dirs_for_names(["a"])
    assert calls == 3


def test_ttl_expiry(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    staged = tmp_path / "stage"
    staged.mkdir()
    calls = 0

    def fake_stage(names: list[str]) -> list[str]:
        nonlocal calls
        calls += 1
        return [str(staged)]

    monkeypatch.setattr(skills_sources, "_stage_skill_source_dirs", fake_stage)
    now = [1000.0]
    monkeypatch.setattr(skills_sources.time, "monotonic", lambda: now[0])
    skills_sources.skill_source_dirs_for_names(["a"])
    now[0] += skills_sources._SOURCE_DIRS_TTL_SEC + 1
    skills_sources.skill_source_dirs_for_names(["a"])
    assert calls == 2


def test_empty_names_short_circuits(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        skills_sources, "_stage_skill_source_dirs", lambda names: pytest.fail("should not stage")
    )
    assert skills_sources.skill_source_dirs_for_names([]) == []
    assert skills_sources.skill_source_dirs_for_names(["  "]) == []
